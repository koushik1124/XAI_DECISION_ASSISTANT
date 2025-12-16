# core_api.py — Clean JSON XAI Assistant with Universal Q&A support
import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

# --- Load API Key ---
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise SystemExit("❌ Missing GROQ_API_KEY")

client = Groq(api_key=API_KEY)

MODEL = "llama-3.3-70b-versatile"

# --- System Prompt: Works for any Q&A or decision task ---
SYSTEM_PROMPT = (
    "You are an Explainable AI Assistant.\n"
    "Always respond in a *single valid JSON object* with these keys:\n"
    "  'final_decision' → direct answer or decision.\n"
    "  'reasoning_summary' → short explanation.\n"
    "  'confidence_score' → High / Medium / Low.\n"
    "  'key_factors' → list of key points (may be empty if not relevant).\n"
    "Rules:\n"
    "- No code blocks like ```json\n"
    "- No trailing text outside JSON\n"
    "- No markdown bullets (*, -, +)\n"
)


def clean_bullets(text: str) -> str:
    """Remove markdown list symbols from reasoning."""
    return re.sub(r"^\s*[\*\-\+]\s*", "", text).strip()


def extract_json(raw: str) -> dict:
    """Safely extract usable JSON from model response."""
    raw = raw.strip()

    # Remove ``` wrappers
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    # Try direct JSON parse
    try:
        return json.loads(raw)
    except:
        pass

    # Try extracting inside text block
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end+1])
        except:
            pass

    # If model still gives wrong format, convert fallback text into JSON schema
    return {
        "final_decision": raw[:300].strip(),
        "reasoning_summary": raw.strip(),
        "confidence_score": "Medium",
        "key_factors": []
    }


def enforce_schema(data: dict) -> dict:
    """Guarantee schema completeness & clean formatting."""
    data.setdefault("final_decision", "Not provided")
    data.setdefault("reasoning_summary", "Not provided")
    data.setdefault("confidence_score", "Medium")
    data.setdefault("key_factors", [])

    # Clean bullets in reasoning
    if isinstance(data["reasoning_summary"], str):
        data["reasoning_summary"] = clean_bullets(data["reasoning_summary"])

    # Clean & flatten key_factors list
    clean_factors = []
    for f in data["key_factors"]:
        if isinstance(f, str):
            clean_factors.append(clean_bullets(f))

    data["key_factors"] = clean_factors[:5]  # limit max 5

    return data


def call_groq_api(query: str):
    return client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        temperature=0.25,
        max_tokens=700
    )


# --- Main Entry Point ---
def get_xai_prediction(user_query: str) -> dict:
    try:
        response = call_groq_api(user_query)
        raw = response.choices[0].message.content

        parsed = extract_json(raw)
        safe_result = enforce_schema(parsed)
        return safe_result

    except Exception as e:
        return {"error": str(e)}


# Debug Test
if __name__ == "__main__":
    test_query = "Who is Elon Musk?"
    print(json.dumps(get_xai_prediction(test_query), indent=4))
