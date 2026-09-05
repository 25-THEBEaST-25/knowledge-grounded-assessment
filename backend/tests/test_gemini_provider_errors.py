"""Tests for Gemini provider-failure handling: rate limits, outages, missing
key, and malformed/wrapped JSON output. None of these hit the real API --
they exercise the translation layer in ``evaluation_service`` that turns SDK
failures into a safe, typed ``GeminiUnavailableError`` instead of a generic
crash or a leaked provider stack trace.
"""

import json

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from backend.app.main import app
from backend.app.services import evaluation_service


client = TestClient(app)


def _api_error(code: int, message: str) -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"message": message}})


def test_missing_api_key_raises_typed_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(evaluation_service, "_client", None)
    with pytest.raises(evaluation_service.GeminiUnavailableError, match="not configured"):
        evaluation_service.get_client()


def test_rate_limit_error_mapped_to_gemini_unavailable(monkeypatch):
    def raise_429(model, contents):
        raise _api_error(429, "quota exceeded")

    fake_client = type("FakeClient", (), {"models": type("M", (), {"generate_content": staticmethod(raise_429)})()})()
    monkeypatch.setattr(evaluation_service, "get_client", lambda: fake_client)

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="rate-limited"):
        evaluation_service._call_gemini("gemini-test", "prompt")


def test_server_error_mapped_to_gemini_unavailable(monkeypatch):
    def raise_500(model, contents):
        raise _api_error(500, "internal error")

    fake_client = type("FakeClient", (), {"models": type("M", (), {"generate_content": staticmethod(raise_500)})()})()
    monkeypatch.setattr(evaluation_service, "get_client", lambda: fake_client)

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="provider returned an error"):
        evaluation_service._call_gemini("gemini-test", "prompt")


def test_network_failure_mapped_to_gemini_unavailable(monkeypatch):
    def raise_network_error(model, contents):
        raise ConnectionError("dns failure")

    fake_client = type("FakeClient", (), {"models": type("M", (), {"generate_content": staticmethod(raise_network_error)})()})()
    monkeypatch.setattr(evaluation_service, "get_client", lambda: fake_client)

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="temporarily unavailable"):
        evaluation_service._call_gemini("gemini-test", "prompt")


def test_extract_json_handles_direct_json():
    payload = {"score": 7, "max_score": 10}
    assert evaluation_service._extract_json(json.dumps(payload)) == payload


def test_extract_json_handles_prose_wrapped_json():
    payload = {"score": 5, "max_score": 10}
    wrapped = f"Sure, here is the evaluation:\n{json.dumps(payload)}\nHope that helps!"
    assert evaluation_service._extract_json(wrapped) == payload


def test_extract_json_raises_on_unparsable_output():
    with pytest.raises(RuntimeError, match="non-JSON output"):
        evaluation_service._extract_json("I cannot evaluate this answer.")


def test_evaluate_endpoint_returns_503_not_500_when_gemini_unavailable(monkeypatch):
    def raise_unavailable(**kwargs):
        raise evaluation_service.GeminiUnavailableError("AI evaluation is temporarily unavailable.")

    import backend.app.api.evaluation as evaluation_api

    monkeypatch.setattr(evaluation_api, "evaluate_answer", raise_unavailable)
    r = client.post(
        "/evaluation/evaluate",
        json={
            "question": "Q",
            "student_answer": "A",
            "model_answer": "M",
            "rubric": {"max_score": 10},
        },
    )
    assert r.status_code == 503
    assert "temporarily unavailable" in r.json()["detail"]
