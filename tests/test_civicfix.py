import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.config import CATEGORIES, CATEGORY_DEPARTMENT_MAP
from app.classifier import classify_issue
from app.guidance_service import get_ai_guidance
from app.letter_generator import generate_letter_content, generate_letter_pdf
from app.rag_engine import EMBEDDING_BATCH_SIZE, EMBEDDING_DIMENSION, _embed_texts

client = TestClient(app)


class TestCivicFixAI(unittest.TestCase):

    @patch.dict(os.environ, {"CIVICFIX_EMBEDDING_API_KEY": "test-key"})
    @patch("google.genai.Client")
    def test_gemini_embeddings_are_batched_and_normalized(self, client_class):
        client = client_class.return_value
        client.models.embed_content.side_effect = lambda **kwargs: SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[3.0, 4.0] + [0.0] * (EMBEDDING_DIMENSION - 2))
                for _ in kwargs["contents"]
            ]
        )

        embeddings = _embed_texts(
            ["guideline"] * (EMBEDDING_BATCH_SIZE + 1),
            task_type="RETRIEVAL_DOCUMENT"
        )

        self.assertEqual(embeddings.shape, (EMBEDDING_BATCH_SIZE + 1, EMBEDDING_DIMENSION))
        self.assertAlmostEqual(float(embeddings[0][0]), 0.6)
        self.assertAlmostEqual(float(embeddings[0][1]), 0.8)
        self.assertEqual(client.models.embed_content.call_count, 2)

    def test_categories_and_departments(self):
        self.assertEqual(len(CATEGORIES), 5)
        for cat in CATEGORIES:
            self.assertIn(cat, CATEGORY_DEPARTMENT_MAP)
            self.assertIn("name", CATEGORY_DEPARTMENT_MAP[cat])
            self.assertIn("jurisdiction", CATEGORY_DEPARTMENT_MAP[cat])

    def test_classifier_clarity(self):
        # Unclear/too short
        res_short = classify_issue("bad")
        self.assertFalse(res_short["is_clear"])
        self.assertIsNotNone(res_short["clarity_message"])

        # Clear description with keyword - Road Damage
        res_clear = classify_issue("There is a massive pothole in the asphalt near the hospital gate causing accidents.")
        self.assertTrue(res_clear["is_clear"])
        self.assertEqual(res_clear["identified_category"], "Road Damage")
        self.assertEqual(res_clear["recommended_department"], "Road Maintenance Authority")

        # Water leakage
        res_water = classify_issue("Severe drinking water pipe burst leaking high pressure water on 2nd cross.")
        self.assertTrue(res_water["is_clear"])
        self.assertEqual(res_water["identified_category"], "Water Leakage")
        self.assertEqual(res_water["recommended_department"], "Water Supply Department")

        # Drainage
        res_drain = classify_issue("The sewer manhole is overflowing with foul wastewater flooding the sidewalk.")
        self.assertTrue(res_drain["is_clear"])
        self.assertEqual(res_drain["identified_category"], "Drainage Overflow")
        self.assertEqual(res_drain["recommended_department"], "Drainage / Sanitation Department")

        # Garbage
        res_waste = classify_issue("Rotting garbage accumulation and trash dumped on the corner of the market.")
        self.assertTrue(res_waste["is_clear"])
        self.assertEqual(res_waste["identified_category"], "Garbage Accumulation")
        self.assertEqual(res_waste["recommended_department"], "Sanitation Department")

        # Streetlight
        res_light = classify_issue("All streetlights and lamp posts are completely dark causing safety issues at night.")
        self.assertTrue(res_light["is_clear"])
        self.assertEqual(res_light["identified_category"], "Streetlight Failure")
        self.assertEqual(res_light["recommended_department"], "Electrical Maintenance Department")

    def test_guidance_rag_flow(self):
        guidance = get_ai_guidance("Pothole damaged road on 4th street", category="Road Damage")
        self.assertTrue(guidance.is_clear)
        self.assertEqual(guidance.identified_category, "Road Damage")
        self.assertEqual(guidance.recommended_department, "Road Maintenance Authority")
        self.assertTrue(len(guidance.procedure_steps) > 0)
        self.assertTrue(len(guidance.required_evidence) > 0)
        self.assertIsNotNone(guidance.jurisdiction_disclaimer)

        if guidance.has_verified_guidance:
            self.assertTrue(len(guidance.sources) > 0)
            src = guidance.sources[0]
            self.assertIsNotNone(src.document_title)
            self.assertGreaterEqual(src.page_number, 1)
            self.assertTrue(len(src.excerpt) > 0)

    def test_letter_generation_and_pdf(self):
        complaint_sample = {
            "complaint_no": "CF-2026-TEST",
            "category": "Road Damage",
            "description": "Deep asphalt crater near bus stand",
            "location": "Main Road, Sector 4",
            "department_name": "Road Maintenance Authority",
            "citizen_name": "Rohan Gupta",
            "citizen_phone": "+91 99999 88888",
            "citizen_email": "rohan@example.com"
        }

        content = generate_letter_content(complaint_sample)
        self.assertEqual(content["complaint_no"], "CF-2026-TEST")
        self.assertIn("Road Damage", content["subject"])
        self.assertIn("Road Maintenance Authority", content["recipient"])

        out_pdf = "data/uploads/temp/test_letter.pdf"
        pdf_path = generate_letter_pdf(content, out_pdf)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 1000)

    def test_api_endpoints(self):
        # 1. Root HTML
        r_root = client.get("/")
        self.assertEqual(r_root.status_code, 200)
        self.assertIn("CivicFix AI", r_root.text)

        # 2. Guidance API
        r_guide = client.post("/api/guidance", json={
            "description": "Massive sewage overflow from choked gutter in front of residential apartments.",
            "category": None
        })
        self.assertEqual(r_guide.status_code, 200)
        data_g = r_guide.json()
        self.assertTrue(data_g["is_clear"])
        self.assertEqual(data_g["identified_category"], "Drainage Overflow")

        # 3. Create Complaint API
        r_comp = client.post("/api/complaints", data={
            "category": "Road Damage",
            "description": "Severe road pavement crack and crater after heavy rainfall.",
            "location": "MG Road, near Metro station",
            "citizen_name": "Test Citizen",
            "citizen_email": "test@example.com",
            "citizen_phone": "+91 91234 56789"
        })
        self.assertEqual(r_comp.status_code, 200)
        comp_data = r_comp.json()
        self.assertEqual(comp_data["status"], "success")
        comp_id = comp_data["complaint_id"]
        complaint_no = comp_data["complaint_no"]

        # 4. List Complaints API
        r_list = client.get("/api/complaints")
        self.assertEqual(r_list.status_code, 200)
        comps = r_list.json()
        self.assertTrue(any(c["id"] == comp_id for c in comps))

        # 5. Get Single Complaint Details
        r_single = client.get(f"/api/complaints/{comp_id}")
        self.assertEqual(r_single.status_code, 200)
        self.assertEqual(r_single.json()["complaint_no"], complaint_no)

        # 6. Letter Preview API
        r_letter = client.get(f"/api/complaints/{comp_id}/letter-preview")
        self.assertEqual(r_letter.status_code, 200)
        self.assertEqual(r_letter.json()["complaint_no"], complaint_no)

        # 7. Admin Overview API
        r_admin_ov = client.get("/api/admin/overview")
        self.assertEqual(r_admin_ov.status_code, 200)
        ov_data = r_admin_ov.json()
        self.assertGreaterEqual(ov_data["total_complaints"], 1)

        # 8. Admin Update Status API
        r_status = client.patch(f"/api/admin/complaints/{comp_id}/status", json={"status": "In Progress"})
        self.assertEqual(r_status.status_code, 200)
        self.assertEqual(r_status.json()["new_status"], "In Progress")

        # 9. Admin List Documents API
        r_docs = client.get("/api/admin/documents")
        self.assertEqual(r_docs.status_code, 200)
        docs = r_docs.json()
        self.assertGreaterEqual(len(docs), 1)

        # 10. Delete Complaint API
        r_del = client.delete(f"/api/complaints/{comp_id}")
        self.assertEqual(r_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()
