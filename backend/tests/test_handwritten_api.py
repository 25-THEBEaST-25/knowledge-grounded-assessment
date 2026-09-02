"""API wiring tests.

PaddleOCR and Gemini are replaced with fakes so these run anywhere. The image
used here is SYNTHETIC (a 1x1 PNG) — it is only a transport payload; it is not
a handwriting-recognition validation.
"""

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.services import ocr_service, pipeline_service
from backend.app.services.ocr_service import OCRLine, OCRResult


def _synthetic_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


class FakeOCR:
    def __init__(self, text: str, conf: float = 0.9):
        self.text, self.conf = text, conf

    def extract(self, image_bytes: bytes) -> OCRResult:
        ocr_service.decode_image(image_bytes)  # still validates the image
        lines = [
            OCRLine(text=t, confidence=self.conf, bbox=[0, i * 10, 100, i * 10 + 8])
            for i, t in enumerate(self.text.splitlines())
        ]
        return ocr_service.build_result(lines, "fake")


def fake_evaluator(question, student_answer, model_answer, rubric):
    return {
        "score": 7,
        "max_score": 10,
        "concept_score": 3,
        "accuracy_score": 2,
        "precision_score": 1,
        "technical_terminology_score": 1,
        "strengths": [f"mentions {student_answer.split()[0]}"],
        "missing_concepts": ["detail"],
        "feedback": f"evaluated: {question}",
        "confidence": 0.8,
    }


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    original = ocr_service.get_ocr_backend()
    ocr_service.set_ocr_backend(
        FakeOCR("Q1. Photosynthesis makes glucose\nQ2. Mitochondria produce ATP", conf=0.9)
    )
    monkeypatch.setattr(pipeline_service.evaluation_service, "evaluate_answer", fake_evaluator)
    yield
    ocr_service.set_ocr_backend(original)


client = TestClient(app)

QUESTIONS = [
    {"question_id": "Q1", "question": "Define photosynthesis", "model_answer": "...", "rubric": {"max_score": 10}},
    {"question_id": "Q2", "question": "Role of mitochondria", "model_answer": "...", "rubric": {"max_score": 10}},
    {"question_id": "Q3", "question": "Unanswered", "model_answer": "...", "rubric": {"max_score": 5}},
]


def test_existing_evaluation_route_preserved():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/evaluation/evaluate" in paths
    body = paths["/evaluation/evaluate"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["$ref"].endswith("EvaluationRequest")
    assert {"/handwritten/ocr", "/handwritten/segment", "/handwritten/evaluate"} <= set(paths)


def test_ocr_endpoint():
    r = client.post("/handwritten/ocr", files={"image": ("a.png", _synthetic_png(), "image/png")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["extracted_text"].startswith("Q1. Photosynthesis")
    assert data["mean_confidence"] == 0.9
    assert len(data["lines"]) == 2


def test_ocr_rejects_bad_image():
    r = client.post("/handwritten/ocr", files={"image": ("a.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_segment_endpoint():
    r = client.post("/handwritten/segment", json={"text": "Q1. a\nQ2. b", "expected_question_ids": ["Q1", "Q2", "Q3"]})
    assert r.status_code == 200
    ids = [s["question_id"] for s in r.json()["segments"]]
    assert ids == ["Q1", "Q2", "Q3"]


def test_full_pipeline():
    r = client.post(
        "/handwritten/evaluate",
        files={"image": ("a.png", _synthetic_png(), "image/png")},
        data={"questions": json.dumps(QUESTIONS)},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ocr_engine"] == "fake"
    assert [s["question_id"] for s in data["segments"]] == ["Q1", "Q2", "Q3"]

    q1, q2, q3 = data["results"]
    assert q1["score"] == 7 and q1["student_answer"] == "Photosynthesis makes glucose"
    assert q1["feedback"] == "evaluated: Define photosynthesis"
    assert q1["strengths"] == ["mentions Photosynthesis"]
    assert q1["combined_confidence"] == round(0.8 * (0.5 + 0.5 * 0.9), 4)
    assert q1["needs_review"] is False
    assert q2["student_answer"] == "Mitochondria produce ATP"
    assert q3["answer_detected"] is False and q3["score"] == 0 and q3["max_score"] == 5
    assert q3["needs_review"] is True

    assert data["total_score"] == 14
    assert data["total_max_score"] == 25
    assert data["needs_review"] is True


def test_pipeline_invalid_questions():
    r = client.post(
        "/handwritten/evaluate",
        files={"image": ("a.png", _synthetic_png(), "image/png")},
        data={"questions": "not json"},
    )
    assert r.status_code == 422


def test_ocr_unavailable_returns_503():
    class Broken:
        def extract(self, image_bytes):
            raise ocr_service.OCRUnavailableError("paddle missing")

    ocr_service.set_ocr_backend(Broken())
    r = client.post("/handwritten/ocr", files={"image": ("a.png", _synthetic_png(), "image/png")})
    assert r.status_code == 503
