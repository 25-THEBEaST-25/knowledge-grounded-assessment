import json
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        _client = genai.Client(api_key=api_key)
    return _client


def evaluate_answer(
    question: str,
    student_answer: str,
    model_answer: str,
    rubric: dict,
) -> dict:

    prompt = f"""
You are an academic assessment evaluator.

Evaluate the student's answer strictly using the supplied
question, model answer, and faculty rubric.

Do not grade using keyword matching alone.

Evaluate:
- conceptual understanding
- factual accuracy
- precision and relevance
- technical terminology
- overall answer quality

QUESTION:
{question}

STUDENT ANSWER:
{student_answer}

MODEL ANSWER:
{model_answer}

FACULTY RUBRIC:
{json.dumps(rubric, indent=2)}

Return ONLY valid JSON in this exact structure:

{{
  "score": 0,
  "max_score": 10,
  "concept_score": 0,
  "accuracy_score": 0,
  "precision_score": 0,
  "technical_terminology_score": 0,
  "strengths": [],
  "missing_concepts": [],
  "feedback": "",
  "confidence": 0.0
}}

The scores must respect the supplied rubric.
Do not exceed the maximum marks for any criterion.
"""

    response = get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    raw_text = response.text.strip()

    print("GEMINI RAW RESPONSE:")
    print(raw_text)

    if not raw_text:
        raise RuntimeError("Gemini returned an empty response.")

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini returned non-JSON output: {raw_text[:1000]}"
        ) from exc