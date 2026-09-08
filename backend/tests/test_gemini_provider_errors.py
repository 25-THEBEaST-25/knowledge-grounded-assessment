"""Tests for Gemini provider-failure handling: rate limits, outages, missing
key, transient-failure retries, and malformed/wrapped JSON output. None of
these hit the real API -- they exercise the translation/retry layer in
``evaluation_service`` that turns SDK failures into a safe, typed
``GeminiUnavailableError`` instead of a generic crash or a leaked provider
stack trace.

``time.sleep`` is monkeypatched to a no-op everywhere a retry path is
exercised, so these tests don't actually wait out the exponential backoff.
"""

import json

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from backend.app.main import app
from backend.app.services import evaluation_service


client = TestClient(app)


@pytest.fixture(autouse=True)
def no_real_backoff(monkeypatch):
    """Every test in this file that triggers a retry would otherwise sleep
    for real (1s, 2s, ...) between attempts. Applied to all tests here for
    simplicity, harmless for tests that never retry."""
    monkeypatch.setattr(evaluation_service.time, "sleep", lambda seconds: None)


def _api_error(code: int, message: str) -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"message": message}})


def _fake_client(fn):
    """Wrap a ``(model, contents) -> response`` callable as a fake genai client."""
    return type("FakeClient", (), {"models": type("M", (), {"generate_content": staticmethod(fn)})()})()


def test_missing_api_key_raises_typed_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(evaluation_service, "_client", None)
    with pytest.raises(evaluation_service.GeminiUnavailableError, match="not configured"):
        evaluation_service.get_client()


def test_rate_limit_error_mapped_to_gemini_unavailable(monkeypatch):
    def raise_429(model, contents):
        raise _api_error(429, "quota exceeded")

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(raise_429))

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="rate-limited"):
        evaluation_service._call_gemini("gemini-test", "prompt")


def test_server_error_mapped_to_gemini_unavailable(monkeypatch):
    def raise_500(model, contents):
        raise _api_error(500, "internal error")

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(raise_500))

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="provider returned an error"):
        evaluation_service._call_gemini("gemini-test", "prompt")


def test_network_failure_mapped_to_gemini_unavailable(monkeypatch):
    def raise_network_error(model, contents):
        raise ConnectionError("dns failure")

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(raise_network_error))

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="temporarily unavailable"):
        evaluation_service._call_gemini("gemini-test", "prompt")


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


def test_succeeds_on_first_attempt_without_retrying(monkeypatch):
    calls = []

    def succeed(model, contents):
        calls.append(1)
        return _FakeResponse('{"score": 5}')

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(succeed))

    result = evaluation_service._call_gemini("gemini-test", "prompt")
    assert result.text == '{"score": 5}'
    assert len(calls) == 1


def test_retries_and_succeeds_after_transient_504(monkeypatch):
    """The exact real-world failure this task is about: ServerError 504
    DEADLINE_EXCEEDED on the first attempt, success on the second."""
    calls = []

    def flaky(model, contents):
        calls.append(1)
        if len(calls) == 1:
            raise genai_errors.ServerError(504, {"error": {"message": "DEADLINE_EXCEEDED"}})
        return _FakeResponse('{"score": 8}')

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(flaky))

    result = evaluation_service._call_gemini("gemini-test", "prompt")
    assert result.text == '{"score": 8}'
    assert len(calls) == 2  # one failure, one successful retry


def test_gives_up_after_max_retries_exhausted(monkeypatch):
    calls = []

    def always_504(model, contents):
        calls.append(1)
        raise genai_errors.ServerError(504, {"error": {"message": "DEADLINE_EXCEEDED"}})

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(always_504))

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="provider returned an error"):
        evaluation_service._call_gemini("gemini-test", "prompt")

    # initial attempt + _MAX_RETRIES retries, never more -- bounded, not infinite
    assert len(calls) == evaluation_service._MAX_RETRIES + 1


def test_retry_count_is_bounded_not_unbounded(monkeypatch):
    """Same as above, phrased as an explicit bound check per the task's
    'never retry indefinitely' requirement."""
    calls = []

    def always_503(model, contents):
        calls.append(1)
        raise _api_error(503, "temporarily overloaded")

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(always_503))

    with pytest.raises(evaluation_service.GeminiUnavailableError):
        evaluation_service._call_gemini("gemini-test", "prompt")

    assert len(calls) <= evaluation_service._MAX_RETRIES + 1


def test_invalid_api_key_error_is_not_retried(monkeypatch):
    """A permanent client/configuration error (bad key -> 401) must fail
    immediately, not burn the retry budget."""
    calls = []

    def raise_401(model, contents):
        calls.append(1)
        raise _api_error(401, "API key not valid")

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(raise_401))

    with pytest.raises(evaluation_service.GeminiUnavailableError, match="provider returned an error"):
        evaluation_service._call_gemini("gemini-test", "prompt")

    assert len(calls) == 1  # no retries for a non-retryable error


def test_malformed_request_error_is_not_retried(monkeypatch):
    """A 400 (e.g. invalid model configuration / bad request) is also
    permanent, not transient -- must not be retried."""
    calls = []

    def raise_400(model, contents):
        calls.append(1)
        raise _api_error(400, "invalid model")

    monkeypatch.setattr(evaluation_service, "get_client", lambda: _fake_client(raise_400))

    with pytest.raises(evaluation_service.GeminiUnavailableError):
        evaluation_service._call_gemini("gemini-test", "prompt")

    assert len(calls) == 1


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
