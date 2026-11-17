import os
import json
import logging
from typing import Dict, Any, List, Optional

from app.config import DATA_DIR

logger = logging.getLogger("civicfix.llm")


class LLMUnavailableError(Exception):
    """Raised when an LLM is required but not configured or failed."""


CONFIG_FILE = DATA_DIR / "llm_config.json"


def get_llm_config() -> Dict[str, Any]:
    """Reads runtime LLM configuration or falls back to environment variables."""
    config = {
        "provider": os.environ.get("LLM_PROVIDER", "auto"),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
        "openai_api_key": os.environ.get("OPENAI_API_KEY", "")
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            logger.warning(f"Could not load llm_config.json: {e}")
    return config


def save_llm_config(provider: str, api_key: str):
    """Saves runtime LLM provider settings."""
    config = get_llm_config()
    config["provider"] = provider
    if provider == "gemini":
        config["gemini_api_key"] = api_key.strip()
    elif provider == "groq":
        config["groq_api_key"] = api_key.strip()
    elif provider == "openai":
        config["openai_api_key"] = api_key.strip()

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


class LLMEngine:
    def __init__(self):
        self.config = get_llm_config()

    def get_active_provider(self) -> str:
        """Determines active LLM provider based on config or keys."""
        cfg = get_llm_config()
        pref = cfg.get("provider", "auto")

        if pref == "gemini" and cfg.get("gemini_api_key"):
            return "Google Gemini"
        elif pref == "groq" and cfg.get("groq_api_key"):
            return "Groq (Llama 3)"
        elif pref == "openai" and cfg.get("openai_api_key"):
            return "OpenAI (GPT-4o)"
        
        # Auto-detect if any valid key is available
        if pref == "auto":
            if cfg.get("gemini_api_key") and len(cfg.get("gemini_api_key", "")) > 15:
                return "Google Gemini"
            if cfg.get("groq_api_key") and len(cfg.get("groq_api_key", "")) > 15:
                return "Groq (Llama 3)"
            if cfg.get("openai_api_key") and len(cfg.get("openai_api_key", "")) > 15:
                return "OpenAI (GPT-4o)"

        return "RAG guidance fallback (no text LLM configured)"

    def generate_rag_guidance(
        self,
        query: str,
        category: str,
        department: str,
        rag_sources: List[Dict[str, Any]],
        jurisdiction_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uses an LLM augmented with retrieved RAG context chunks
        to produce comprehensive, verified grievance guidance.
        """
        provider = self.get_active_provider()
        logger.info(f"Generating RAG guidance using LLM provider: {provider}")

        # Assemble retrieved RAG context
        context_blocks = []
        for i, src in enumerate(rag_sources, 1):
            context_blocks.append(
                f"[Source {i}: {src.get('document_title', 'Government Guideline')} | Page {src.get('page_number', 1)}]\n"
                f"\"{src.get('excerpt', '')}\""
            )
        rag_context = "\n\n".join(context_blocks) if context_blocks else "No specific document section retrieved."

        # 1. Try Gemini if configured
        if "Gemini" in provider:
            try:
                res = self._call_gemini_guidance(query, category, department, rag_context, jurisdiction_notes)
                if res:
                    res["llm_provider"] = provider
                    return res
            except Exception as e:
                logger.error(f"Gemini LLM error: {e}. Falling back to RAG guidance.")

        # 2. Try Groq if configured
        if "Groq" in provider:
            try:
                res = self._call_groq_guidance(query, category, department, rag_context, jurisdiction_notes)
                if res:
                    res["llm_provider"] = provider
                    return res
            except Exception as e:
                logger.error(f"Groq LLM error: {e}. Falling back to RAG guidance.")

        # 3. Try OpenAI if configured
        if "OpenAI" in provider:
            try:
                res = self._call_openai_guidance(query, category, department, rag_context, jurisdiction_notes)
                if res:
                    res["llm_provider"] = provider
                    return res
            except Exception as e:
                logger.error(f"OpenAI LLM error: {e}. Falling back to RAG guidance.")

        # 4. Use the existing structured fallback over retrieved guideline text.
        res = self._rule_based_rag_guidance(query, category, department, rag_sources, jurisdiction_notes)
        res["llm_provider"] = "RAG guidance fallback (no text LLM configured)"
        return res

    def generate_complaint_letter(
        self,
        complaint: Dict[str, Any],
        rag_sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Letter text is written entirely by the LLM (no hard-coded template).
        Raises LLMUnavailableError if no LLM key is configured or the call fails.
        """
        from datetime import datetime
        provider = self.get_active_provider()
        rag_context = " ".join(src.get("excerpt", "") for src in rag_sources)

        if "Gemini" in provider:
            call = self._call_gemini_letter
        elif "Groq" in provider:
            call = self._call_groq_letter
        elif "OpenAI" in provider:
            call = self._call_openai_letter
        else:
            raise LLMUnavailableError(
                "Letter generation needs an LLM. Open AI / LLM Settings, choose Gemini, Groq or OpenAI, "
                "paste your API key and click Save & Activate."
            )

        try:
            letter = call(complaint, rag_context)
        except Exception as e:
            logger.error(f"{provider} letter generation failed: {e}")
            raise LLMUnavailableError(f"{provider} could not generate the letter: {e}")

        letter["complaint_no"] = complaint.get("complaint_no")
        letter["date"] = datetime.now().strftime("%B %d, %Y")
        letter["citizen_name"] = complaint.get("citizen_name", "Concerned Citizen")
        letter["citizen_phone"] = complaint.get("citizen_phone") or ""
        letter["citizen_email"] = complaint.get("citizen_email") or ""
        letter["llm_provider"] = provider
        return letter

    # ==========================================
    # PROVIDER CALLERS
    # ==========================================

    def _call_gemini_guidance(self, query: str, category: str, department: str, rag_context: str, jurisdiction_notes: str) -> Optional[Dict[str, Any]]:
        cfg = get_llm_config()
        api_key = cfg.get("gemini_api_key")
        if not api_key:
            return None
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""You are CivicFix AI, an authoritative public grievance guidance engine.
Analyze the citizen's complaint using ONLY the official municipal guidelines provided below.

OFFICIAL GOVERNMENT GUIDELINE CONTEXT:
{rag_context}

CITIZEN'S PROBLEM:
"{query}"

CATEGORY: {category}
DEPARTMENT: {department}
JURISDICTION: {jurisdiction_notes}

Respond strictly in valid JSON format with this exact structure:
{{
  "ai_analysis": "2-3 sentences explaining the nature of the civic issue, safety hazards, and why it falls under {department}.",
  "procedure_steps": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ...",
    "Step 4: ..."
  ],
  "required_evidence": [
    "Evidence 1...",
    "Evidence 2...",
    "Evidence 3..."
  ],
  "estimated_turnaround": "Resolution timeframe as stated in guidelines (e.g., 24-48 hours)."
}}"""
        for m in ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                )
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                return json.loads(text.strip())
            except Exception as e:
                logger.warning(f"Gemini call with {m} failed: {e}")
        return None

    def _call_groq_guidance(self, query: str, category: str, department: str, rag_context: str, jurisdiction_notes: str) -> Optional[Dict[str, Any]]:
        cfg = get_llm_config()
        api_key = cfg.get("groq_api_key")
        if not api_key:
            return None
        from groq import Groq
        client = Groq(api_key=api_key)

        prompt = f"""You are CivicFix AI, an authoritative public grievance guidance engine.
Analyze the citizen's complaint using ONLY the official municipal guidelines provided below.

OFFICIAL GOVERNMENT GUIDELINE CONTEXT:
{rag_context}

CITIZEN'S PROBLEM:
"{query}"

CATEGORY: {category}
DEPARTMENT: {department}

Respond strictly in valid JSON with keys: 'ai_analysis', 'procedure_steps' (array), 'required_evidence' (array), 'estimated_turnaround'."""

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)

    def _call_openai_guidance(self, query: str, category: str, department: str, rag_context: str, jurisdiction_notes: str) -> Optional[Dict[str, Any]]:
        cfg = get_llm_config()
        api_key = cfg.get("openai_api_key")
        if not api_key:
            return None
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""You are CivicFix AI. Use this official municipal guideline context to guide the citizen.
CONTEXT:
{rag_context}

PROBLEM: "{query}" | CATEGORY: {category} | DEPT: {department}

Respond strictly in valid JSON with: ai_analysis, procedure_steps (list), required_evidence (list), estimated_turnaround."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def _rule_based_rag_guidance(
        self,
        query: str,
        category: str,
        department: str,
        rag_sources: List[Dict[str, Any]],
        jurisdiction_notes: Optional[str]
    ) -> Dict[str, Any]:
        """
        Extracts structured guidance from the guideline chunks already ranked by RAG.
        """
        import re

        combined_rag_text = " ".join([src.get("excerpt", "") for src in rag_sources])
        sop_match = re.search(r"\(SOP-[A-Z0-9\-]+\)", combined_rag_text)
        sop_code = sop_match.group(0) if sop_match else "(Municipal Citizen Charter SOP)"

        # The first retrieved chunk is already the highest-scoring FAISS result.
        best_rag_sentence = ""
        if combined_rag_text.strip():
            sentences = [
                s.strip() for s in re.split(r"(?<=[.!?])\s+", combined_rag_text)
                if len(s.strip()) > 25
            ]
            if sentences:
                best_rag_sentence = sentences[0]

        analysis = (
            f"Based on your report (\"{query[:90]}\"), this grievance is classified under '{category}' "
            f"{sop_code} and routed to the {department}. "
        )
        if best_rag_sentence:
            analysis += f"According to retrieved municipal guidelines: \"{best_rag_sentence}\""
        else:
            analysis += (
                f"As per municipal administrative guidelines, field inspection and remedial action fall directly "
                f"under the operational scope of the {department}."
            )

        # Extract procedures from RAG chunks
        procedures = []
        if combined_rag_text:
            numbered = re.findall(r"\(\d+\)\s*([^.()]+(?:\.[^.()]+)?\.)", combined_rag_text)
            for idx, item in enumerate(numbered[:4], 1):
                clean_item = item.strip().rstrip(".")
                if len(clean_item) > 10:
                    procedures.append(f"Step {idx} (RAG {sop_code}): {clean_item}.")

        if not procedures:
            procedures = [
                f"Step 1: Document the {category.lower()} with clear photographs capturing visible damage and street landmarks.",
                f"Step 2: Register the formal grievance with the {department} under {sop_code}.",
                "Step 3: A designated ward engineer or nodal inspector will verify the site within 24 hours.",
                "Step 4: Track complaint resolution via your unique reference number for statutory redressal."
            ]

        # Extract required evidence from RAG chunks
        evidence = []
        ev_match = re.search(
            r"Required (?:Documents & )?Evidence:\s*([^.]+)\.",
            combined_rag_text,
            re.IGNORECASE
        )
        if ev_match:
            ev_clause = ev_match.group(1).strip()
            parts = [p.strip() for p in re.split(r",|\band\b", ev_clause) if len(p.strip()) > 12]
            for p in parts[:4]:
                evidence.append(p[0].upper() + p[1:])

        if not evidence:
            evidence = [
                f"Clear close-up photograph showing the exact extent of {category.lower()}",
                "Wide-angle photograph showing street name, building number, or prominent landmark",
                "Exact location description or nearby GPS landmark coordinate",
                "Approximate duration / date when the civic issue was first observed"
            ]

        # Extract turnaround window from RAG chunks
        turnaround = "48 to 72 hours under standard Citizen Charter guidelines."
        tw_match = re.search(
            r"(?:Redressal Window|Turnaround Time):\s*([^.]+)\.",
            combined_rag_text,
            re.IGNORECASE
        )
        if tw_match:
            turnaround = tw_match.group(1).strip() + f" {sop_code}."

        return {
            "ai_analysis": analysis,
            "procedure_steps": procedures[:4],
            "required_evidence": evidence,
            "estimated_turnaround": turnaround
        }

    def _letter_prompt(self, complaint: Dict[str, Any], rag_context: str) -> str:
        return f"""You are an expert civic grievance letter drafter.
Write a formal, polite complaint letter from a citizen to the responsible municipal department.
Use ONLY the facts below. Do not invent names, numbers, dates or promises.
Mention the SOP code and the resolution timeframe ONLY if they appear in the guideline context.

Complaint No: {complaint.get('complaint_no')}
Category: {complaint.get('category')}
Problem description: {complaint.get('description')}
Location: {complaint.get('location')}
Department: {complaint.get('department_name')}
Citizen name: {complaint.get('citizen_name')}
Citizen phone: {complaint.get('citizen_phone') or 'Not provided'}
Citizen email: {complaint.get('citizen_email') or 'Not provided'}

OFFICIAL GUIDELINE CONTEXT (retrieved by RAG):
{rag_context[:1200]}

Respond strictly as JSON with keys:
"subject": one-line subject that includes the complaint number,
"recipient": address block starting with "To,",
"body": full letter from "Respected Sir / Madam," to the closing "Yours sincerely," followed by the citizen name, phone and email."""

    @staticmethod
    def _parse_letter_json(text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        for k in ("subject", "recipient", "body"):
            if not data.get(k):
                raise ValueError(f"LLM letter missing '{k}'")
        return data

    def _call_gemini_letter(self, complaint, rag_context):
        api_key = get_llm_config().get("gemini_api_key")
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = self._letter_prompt(complaint, rag_context)
        last = None
        for m in ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
            try:
                r = client.models.generate_content(model=m, contents=prompt)
                return self._parse_letter_json(r.text)
            except Exception as e:
                last = e
                logger.warning(f"Letter with {m} failed: {e}")
        raise RuntimeError(f"Gemini letter generation failed: {last}")

    def _call_groq_letter(self, complaint, rag_context):
        from groq import Groq
        client = Groq(api_key=get_llm_config().get("groq_api_key"))
        r = client.chat.completions.create(
            messages=[{"role": "user", "content": self._letter_prompt(complaint, rag_context)}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
        )
        return self._parse_letter_json(r.choices[0].message.content)

    def _call_openai_letter(self, complaint, rag_context):
        from openai import OpenAI
        client = OpenAI(api_key=get_llm_config().get("openai_api_key"))
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": self._letter_prompt(complaint, rag_context)}],
            response_format={"type": "json_object"},
        )
        return self._parse_letter_json(r.choices[0].message.content)

# Singleton LLM Engine
llm_engine = LLMEngine()
