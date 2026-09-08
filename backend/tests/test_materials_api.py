"""API-level tests for POST /materials/ingest."""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_materials_route_registered():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/materials/ingest" in paths


def test_ingest_txt_model_answer_via_api():
    r = client.post(
        "/materials/ingest",
        files={"file": ("answers.txt", b"Q1. Explain TCP.\nTCP is a connection-oriented transport protocol.", "text/plain")},
        data={"kind": "model_answer"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["extraction_engine"] == "txt"
    assert body["questions"][0]["question_id"] == "Q1"
    assert "TCP" in body["questions"][0]["model_answer"]


def test_ingest_rejects_invalid_kind():
    r = client.post(
        "/materials/ingest",
        files={"file": ("a.txt", b"Q1. x", "text/plain")},
        data={"kind": "bogus"},
    )
    assert r.status_code == 422


def test_ingest_rejects_unsupported_extension():
    r = client.post(
        "/materials/ingest",
        files={"file": ("answers.xlsx", b"whatever", "application/octet-stream")},
        data={"kind": "model_answer"},
    )
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_ingest_rejects_empty_file():
    r = client.post(
        "/materials/ingest",
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"kind": "model_answer"},
    )
    assert r.status_code == 400
