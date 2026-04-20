from temporalio import activity
import json
from app.services.llm_service import LLMService
from app.schemas.pydantic_models import KnowledgeBaseData

llm = LLMService()


def build_prompt(chunk: str) -> str:
    return f"""
Extract structured knowledge from the markdown chunk.

Rules:
- Keep summary concise (2-4 sentences)
- key_points must be bullet-style facts
- entities must be important concepts only
- relationships should describe connections

Return STRICT JSON ONLY:
{{
  "summary": "",
  "key_points": [],
  "entities": [],
  "relationships": []
}}

Content:
{chunk}
"""


def normalize_list(value):
    """
    Ensures field is always a list of strings.
    """
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [value.strip()]
    return []


import re

def safe_parse_kb(raw: str) -> dict:
    """
    Safely parse and validate KB output by extracting the first JSON block.
    """
    # 1. Clean up backticks and whitespace
    clean_raw = raw.strip().replace("```json", "").replace("```", "").strip()
    
    # 2. Try to find/extract the main JSON object {...}
    json_match = re.search(r'\{.*\}', clean_raw, re.DOTALL)
    if json_match:
        clean_raw = json_match.group(0)

    try:
        data = json.loads(clean_raw)
    except Exception:
        # Fallback: Treat as plain text summary
        return {
            "summary": raw.strip()[:1000],
            "key_points": [],
            "entities": [],
            "relationships": []
        }

    try:
        # Standardize return structure
        kb = KnowledgeBaseData(
            summary=str(data.get("summary", "")).strip(),
            key_points=normalize_list(data.get("key_points")),
            entities=normalize_list(data.get("entities")),
            relationships=normalize_list(data.get("relationships")),
        )
        # Use model_dump() for Pydantic v2
        return kb.model_dump()

    except Exception:
        return {
            "summary": "Parsing error on: " + clean_raw[:200],
            "key_points": [],
            "entities": [],
            "relationships": []
        }


@activity.defn
def generate_kb_chunk(chunk: dict) -> dict:
    """
    Generate structured KB entry for a single chunk.
    """

    prompt = build_prompt(chunk["content"])
    # Simple schema for better grammar compatibility
    simple_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "entities": {"type": "array", "items": {"type": "string"}},
            "relationships": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["summary", "key_points", "entities", "relationships"]
    }
    
    raw = llm.generate(prompt, schema=simple_schema)
    parsed = safe_parse_kb(raw)

    return {
        "chunk_index": chunk["chunk_index"],
        "kb": parsed
    }