from temporalio import activity
import json
from app.services.llm_service import LLMService
from app.schemas.pydantic_models import QAPair

llm = LLMService()


def build_prompt(content: str) -> str:
    return f"""
Generate high-quality Q&A pairs from the content below.

Rules:
- Questions must be specific and meaningful
- Avoid duplicates
- Cover key concepts

Return STRICT JSON:
[
  {{
    "question": "",
    "answer": "",
    "difficulty": "easy|medium|hard"
  }}
]

Content:
{content}
"""


import re

def safe_parse_qa(raw: str):
    """
    Safely parse LLM output into validated QA pairs.
    """
    # Clean possible markdown bars
    clean_raw = raw.strip().replace("```json", "").replace("```", "").strip()
    
    # 1. Try direct parse (Grammar sampling should make this work)
    try:
        data = json.loads(clean_raw)
    except Exception:
        # 2. Fallback: Try regex to extract block
        json_match = re.search(r'\[.*\]', clean_raw, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
            except Exception:
                print(f"❌ Failed to parse QA even with regex. Raw first 50: {raw[:50]}")
                return []
        else:
            return []

    try:
        if not isinstance(data, list):
             data = [data] if isinstance(data, dict) else []

        valid_qas = []
        for item in data:
            try:
                qa = QAPair(
                    question=str(item.get("question", "")).strip(),
                    answer=str(item.get("answer", "")).strip(),
                    difficulty=str(item.get("difficulty", "medium")).lower()
                )
                valid_qas.append(qa.model_dump())
            except Exception:
                continue

        return valid_qas

    except Exception as e:
        print(f"❌ Error during QA list validation: {e}")
        return []


@activity.defn
def generate_qa_chunk(chunk: dict) -> list:
    """
    Generate QA pairs for a single chunk.
    """
    prompt = build_prompt(chunk["content"])
    # Simple schema for better grammar compatibility
    simple_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "difficulty": {"enum": ["easy", "medium", "hard"]}
            },
            "required": ["question", "answer", "difficulty"]
        }
    }
    
    raw = llm.generate(prompt, schema=simple_schema)
    print(f"🤖 QA Raw: {raw[:100]}...") 
    parsed_qas = safe_parse_qa(raw)
    print(f"✅ QA Parsed: {len(parsed_qas)} pairs")
    return parsed_qas