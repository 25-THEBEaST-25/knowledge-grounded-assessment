"""Tests for the OCR-corruption-tolerant prompt and the visual (image)
fallback in evaluate_answer (A5/A6). None of these hit the real API --
they capture what `_call_gemini` was called with.
"""

import json

from backend.app.services import evaluation_service


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


def _stub_call_gemini(monkeypatch, capture: dict):
    def fake(model_name, contents):
        capture["model_name"] = model_name
        capture["contents"] = contents
        return _FakeResponse(json.dumps({"score": 5, "confidence": 0.9}))

    monkeypatch.setattr(evaluation_service, "_call_gemini", fake)


def test_default_call_has_no_ocr_caveat_and_plain_string_contents(monkeypatch):
    """The plain-text /evaluation/evaluate endpoint never passes
    ocr_confidence/image_bytes -- this must reproduce the exact prompt shape
    that existed before the visual-fallback work, i.e. a plain string, no
    OCR-caveat clause."""
    capture: dict = {}
    _stub_call_gemini(monkeypatch, capture)

    evaluation_service.evaluate_answer(
        question="Q", student_answer="A", model_answer="M", rubric={"max_score": 10}
    )

    assert isinstance(capture["contents"], str)
    assert "OCR" not in capture["contents"]


def test_low_ocr_confidence_adds_caveat_clause(monkeypatch):
    capture: dict = {}
    _stub_call_gemini(monkeypatch, capture)

    evaluation_service.evaluate_answer(
        question="Q",
        student_answer="A CK packet",
        model_answer="M",
        rubric={"max_score": 10},
        ocr_confidence=0.4,
    )

    assert isinstance(capture["contents"], str)
    assert "OCR confidence: 0.40" in capture["contents"]
    assert "A CK" in capture["contents"]  # the example from the spec is present verbatim
    assert "do not invent content" in capture["contents"].lower()


def test_high_ocr_confidence_omits_caveat_clause(monkeypatch):
    """ocr_confidence=1.0 (a clean OCR read) should not add the caveat --
    only genuinely uncertain OCR gets the disclaimer."""
    capture: dict = {}
    _stub_call_gemini(monkeypatch, capture)

    evaluation_service.evaluate_answer(
        question="Q", student_answer="A", model_answer="M", rubric={"max_score": 10}, ocr_confidence=1.0
    )

    assert "OCR confidence" not in capture["contents"]


def test_image_bytes_builds_multimodal_contents(monkeypatch):
    capture: dict = {}
    _stub_call_gemini(monkeypatch, capture)

    fake_image = b"\x89PNG\r\n\x1a\n" + b"0" * 20  # not a real PNG, just needs to be bytes here

    evaluation_service.evaluate_answer(
        question="Q",
        student_answer="A",
        model_answer="M",
        rubric={"max_score": 10},
        ocr_confidence=0.3,
        image_bytes=fake_image,
    )

    contents = capture["contents"]
    assert isinstance(contents, list)
    assert len(contents) == 2
    # First part is the text prompt (with the image-guidance clause too)
    assert contents[0].text is not None
    assert "attached because OCR confidence was low" in contents[0].text
    # Second part carries the raw image bytes
    assert contents[1].inline_data.data == fake_image
    assert contents[1].inline_data.mime_type == "image/png"


def test_no_image_bytes_never_builds_multimodal_contents(monkeypatch):
    """Sanity check for the confidence gate living in the caller
    (pipeline_service), not here: evaluate_answer itself must never attach an
    image unless explicitly given one, regardless of ocr_confidence."""
    capture: dict = {}
    _stub_call_gemini(monkeypatch, capture)

    evaluation_service.evaluate_answer(
        question="Q", student_answer="A", model_answer="M", rubric={"max_score": 10}, ocr_confidence=0.1
    )

    assert isinstance(capture["contents"], str)
