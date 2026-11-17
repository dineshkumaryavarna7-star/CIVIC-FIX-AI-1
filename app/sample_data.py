import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from sqlalchemy.orm import Session

from app.config import (
    DEFAULT_DEPARTMENTS,
    GUIDELINES_DIR,
    BASE_DIR
)
from app.models import Department, Document, User
from app.rag_engine import rag_engine


def seed_departments_and_users(db: Session):
    """Seeds default departments and demo users if not present."""
    # Seed departments
    existing_depts = db.query(Department).all()
    if not existing_depts:
        for dept_data in DEFAULT_DEPARTMENTS:
            dept = Department(
                name=dept_data["name"],
                code=dept_data["code"],
                contact_email=dept_data["contact_email"],
                phone=dept_data["phone"],
                jurisdiction_notes=dept_data["jurisdiction_notes"]
            )
            db.add(dept)
        db.commit()

    # Seed default demo citizen and admin users
    if not db.query(User).filter(User.username == "citizen_demo").first():
        citizen = User(
            username="citizen_demo",
            email="citizen@civicfix.local",
            full_name="Rajesh Sharma",
            phone="+91 98765 43210",
            role="citizen"
        )
        db.add(citizen)

    if not db.query(User).filter(User.username == "admin_demo").first():
        admin = User(
            username="admin_demo",
            email="admin@civicfix.local",
            full_name="Municipal Chief Administrator",
            phone="+91 11 2345 6789",
            role="admin"
        )
        db.add(admin)

    db.commit()


def create_sample_guideline_pdf(file_path: str) -> str:
    """
    Creates a comprehensive official government guideline PDF
    covering all 5 civic grievance categories with exact page numbers.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=8
    )

    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )

    elements = []

    # Page 1: Overview & Road Damage
    elements.append(Paragraph("MUNICIPAL CIVIC GRIEVANCE CITIZEN CHARTER & GUIDELINES", title_style))
    elements.append(Paragraph("Ministry of Urban Affairs & Municipal Administration | Standard Operating Procedures 2026", styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1E3A8A'), spaceAfter=14))

    elements.append(Paragraph("Section 1: General Citizen Grievance Filing Framework", section_style))
    elements.append(Paragraph(
        "Citizens have the statutory right under the Municipal Public Services Guarantee Act to report civic infrastructure defects. "
        "Every registered complaint must be assigned a unique tracking number, acknowledged within 24 hours, and inspected by the "
        "designated ward engineer or nodal officer.",
        body_style
    ))

    elements.append(Paragraph("Section 2: Road Damage and Pothole Rectification Protocol (SOP-RD-01)", section_style))
    elements.append(Paragraph(
        "Responsible Department: Road Maintenance Authority. Scope covers potholes, fractured bituminous layers, collapsed pavers, "
        "and pavement cave-ins. Procedures: (1) Mandatory visual documentation showing depth of pothole and width relative to the road. "
        "(2) Recording of landmark and street intersection name. (3) Submission via portal or ward grievance counter. "
        "Required Evidence: Minimum of two clear photographs (one close-up showing crater depth, one wide-angle showing street context) "
        "and exact GPS location or street cross-junction. Turnaround Time: Potholes on arterial roads must be filled using cold-mix asphalt "
        "within 48 to 72 hours of verification.",
        body_style
    ))

    # Page 2: Drainage & Sewage
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Section 3: Drainage and Sewer Overflow Rectification (SOP-DS-02)", section_style))
    elements.append(Paragraph(
        "Responsible Department: Drainage / Sanitation Department. Scope covers overflowing manholes, blocked storm-water drains, "
        "septic line backflow, and stagnant wastewater accumulation. Procedures: (1) Immediate classification of public health risk. "
        "(2) Desilting jetting machine deployment within 24 hours. (3) Disinfection of contaminated public surfaces with bleaching powder. "
        "Required Documents & Evidence: Visual proof of overflowing drain, mention of house or commercial building number affected, "
        "and note if foul smell or water-logging poses vector-borne disease danger. Redressal Window: Emergency manhole clearance within "
        "24 hours; major drain desilting completed within 5 business days.",
        body_style
    ))

    # Page 3: Garbage Accumulation & Streetlights
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Section 4: Solid Waste Management and Garbage Accumulation (SOP-SWM-03)", section_style))
    elements.append(Paragraph(
        "Responsible Department: Sanitation Department. Scope covers uncollected municipal solid waste, community bin overflow, "
        "unauthorized street dumping, and organic waste decay. Procedures: (1) Sanitation inspector site visit within 12 hours. "
        "(2) Mechanical compactor or tipper vehicle dispatch. (3) Disinfection and awareness notice at recurring black spots. "
        "Required Evidence: Clear photograph showing waste volume, specify if garbage is obstructing traffic, and report duration "
        "since last collection. Redressal Window: Community bins cleared within 12 to 24 hours; bulk dump site cleared in 48 hours.",
        body_style
    ))

    # Page 4: Streetlights & Water Leakage
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Section 5: Streetlight Failure and Public Lighting Infrastructure (SOP-SL-04)", section_style))
    elements.append(Paragraph(
        "Responsible Department: Electrical Maintenance Department. Scope covers non-functioning streetlights, damaged lamp posts, "
        "flickering LED fixtures, day-burning lights, and exposed feeder wires. Procedures: (1) Locate unique alphanumeric pole identifier. "
        "(2) Dispatch maintenance lineman team. (3) Replace LED driver, bulb, or repaired underground cable. "
        "Required Evidence: Pole ID number stamped on the post, exact street name, and whether a single pole or continuous dark zone. "
        "Redressal Window: Single lamp failure rectified in 48 hours; cable break or dark zone rectified within 72 hours.",
        body_style
    ))

    elements.append(Paragraph("Section 6: Drinking Water Pipeline Leakage & Rupture (SOP-WL-05)", section_style))
    elements.append(Paragraph(
        "Responsible Department: Water Supply Department. Scope encompasses potable pipeline bursts, main valve leakage, broken public taps, "
        "and contamination seepage into distribution mains. Procedures: (1) Immediate reporting to 24/7 Water Control Room. "
        "(2) Isolation of nearest gate valve to prevent water wastage. (3) Trenching and pipeline collar clamping or pipe replacement. "
        "Required Evidence: Photograph of active water leak, estimate of flow rate (trickle vs gushing stream), street address, "
        "and whether residential water supply is disrupted. Redressal Window: Major mains leak contained within 6 to 12 hours; minor valve leaks repaired within 24 hours.",
        body_style
    ))

    doc.build(elements)
    return file_path


def initialize_sample_data_if_needed(db: Session):
    """
    Initializes default departments, and if no documents are present in database,
    creates the sample guideline PDF and registers it into RAG.
    """
    seed_departments_and_users(db)

    # Check if any documents exist
    documents = db.query(Document).all()
    doc_count = len(documents)
    if doc_count == 0:
        sample_pdf_path = str(GUIDELINES_DIR / "Urban_Civic_Grievance_Guidelines_2026.pdf")
        if not os.path.exists(sample_pdf_path):
            create_sample_guideline_pdf(sample_pdf_path)

        file_size = os.path.getsize(sample_pdf_path)
        doc = Document(
            title="Urban Civic Grievance Guidelines 2026",
            filename="Urban_Civic_Grievance_Guidelines_2026.pdf",
            file_path=sample_pdf_path,
            file_size=file_size,
            page_count=2,
            chunk_count=0,
            category_tag="General Civic Guidelines",
            uploaded_at=datetime.utcnow()
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Chunk and embed into RAG
        chunks = rag_engine.extract_and_chunk_pdf(
            pdf_path=sample_pdf_path,
            doc_id=doc.id,
            title=doc.title,
            filename=doc.filename,
            category_tag=doc.category_tag
        )
        doc.chunk_count = len(chunks)
        db.commit()

        rag_engine.add_document_chunks(chunks)
    elif rag_engine.needs_rebuild:
        index_documents = []
        for document in documents:
            if (
                document.filename == "Urban_Civic_Grievance_Guidelines_2026.pdf"
                and not os.path.exists(document.file_path)
            ):
                create_sample_guideline_pdf(document.file_path)
            if not os.path.exists(document.file_path):
                raise RuntimeError(
                    f"RAG source file '{document.file_path}' is missing. "
                    "Restore the file from persistent object storage before rebuilding the index."
                )
            index_documents.append({
                "id": document.id,
                "title": document.title,
                "filename": document.filename,
                "file_path": document.file_path,
                "category_tag": document.category_tag,
            })
        rag_engine.rebuild_index_from_documents(index_documents)
