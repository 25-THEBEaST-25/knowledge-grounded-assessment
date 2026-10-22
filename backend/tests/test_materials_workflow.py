"""Comprehensive tests for Faculty Material Ingestion, Review, Approval,
and Grounded Retrieval (Stages 3 and 4).
"""

import io
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.services.knowledge_repository import (
    get_knowledge_repository,
    reset_knowledge_repository,
)
from backend.app.services.orchestrator_service import evaluate_with_orchestrator
from backend.app.services.retrieval_service import (
    register_approved_reference_material,
    retrieve_grounding_sources,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_knowledge_repo():
    reset_knowledge_repository()
    yield
    reset_knowledge_repository()


def test_get_supported_material_types():
    """Verify GET /materials/types returns all 5 required academic resource categories."""
    res = client.get("/materials/types")
    assert res.status_code == 200, res.text
    data = res.json()

    kinds = {item["kind"] for item in data["supported_kinds"]}
    assert "question_paper" in kinds
    assert "model_answer" in kinds
    assert "rubric" in kinds
    assert "notes" in kinds
    assert "pyq" in kinds

    assert ".pdf" in data["supported_extensions"]
    assert ".docx" in data["supported_extensions"]
    assert ".txt" in data["supported_extensions"]
    assert data["max_upload_mb"] == 15


def test_ingest_question_paper_and_model_answer_txt():
    """Verify ingestion of question papers and model answers."""
    qp_content = b"Q1. Describe Dijkstra's algorithm. [10 marks]\nQ2. Explain Bellman-Ford. [5 marks]"
    r_qp = client.post(
        "/materials/ingest",
        files={"file": ("qp.txt", qp_content, "text/plain")},
        data={"kind": "question_paper"},
    )
    assert r_qp.status_code == 200, r_qp.text
    qp_data = r_qp.json()
    assert len(qp_data["questions"]) == 2
    assert qp_data["questions"][0]["question_id"] == "Q1"
    assert qp_data["questions"][0]["max_score"] == 10.0
    assert "Dijkstra" in qp_data["questions"][0]["question_text"]
    assert qp_data["questions"][0]["model_answer"] == ""

    ma_content = b"Q1. Dijkstra computes shortest paths from a single source using a priority queue. [10 marks]"
    r_ma = client.post(
        "/materials/ingest",
        files={"file": ("ma.txt", ma_content, "text/plain")},
        data={"kind": "model_answer"},
    )
    assert r_ma.status_code == 200, r_ma.text
    ma_data = r_ma.json()
    assert len(ma_data["questions"]) == 1
    assert ma_data["questions"][0]["question_id"] == "Q1"
    assert "priority queue" in ma_data["questions"][0]["model_answer"]
    assert ma_data["questions"][0]["question_text"] == ""


def test_ingest_rubric_file():
    """Verify rubric ingestion parses criteria and mark allocations."""
    rubric_content = (
        b"Q1. Dijkstra\n"
        b"- Algorithm concept and priority queue (4 marks)\n"
        b"- Relaxation step and time complexity (6 marks)\n"
    )
    r = client.post(
        "/materials/ingest",
        files={"file": ("rubric.txt", rubric_content, "text/plain")},
        data={"kind": "rubric"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["document_type"] == "rubric"
    assert "rubric_criteria" in data and data["rubric_criteria"] is not None
    assert "Q1" in data["rubric_criteria"]
    crits = data["rubric_criteria"]["Q1"]
    assert len(crits) == 2
    assert crits[0]["max_marks"] == 4.0
    assert crits[1]["max_marks"] == 6.0


def test_ingest_lecture_notes_and_pyq():
    """Verify lecture notes and PYQs ingestion."""
    notes_content = (
        b"Algorithms Lecture 14: Shortest Paths.\n\n"
        b"Dijkstra algorithm works for non-negative edge weights.\n\n"
        b"Time complexity using Fibonacci heap is O(V log V + E)."
    )
    r_notes = client.post(
        "/materials/ingest",
        files={"file": ("lecture14_notes.txt", notes_content, "text/plain")},
        data={"kind": "notes"},
    )
    assert r_notes.status_code == 200, r_notes.text
    notes_data = r_notes.json()
    assert notes_data["document_type"] == "notes"
    assert len(notes_data["sections_preview"]) >= 2
    assert "Dijkstra algorithm" in notes_data["raw_text_preview"]

    pyq_content = b"Q1. (2024 Exam) Explain Dijkstra with an example. [10 marks]"
    r_pyq = client.post(
        "/materials/ingest",
        files={"file": ("pyq_2024.txt", pyq_content, "text/plain")},
        data={"kind": "pyq"},
    )
    assert r_pyq.status_code == 200, r_pyq.text
    pyq_data = r_pyq.json()
    assert pyq_data["document_type"] == "pyq"
    assert pyq_data["questions"][0]["question_id"] == "Q1"
    assert pyq_data["questions"][0]["max_score"] == 10.0


def test_unsupported_formats_and_empty_file():
    """Verify rejection of unsupported formats and empty files."""
    r_xlsx = client.post(
        "/materials/ingest",
        files={"file": ("sheet.xlsx", b"content", "application/octet-stream")},
        data={"kind": "question_paper"},
    )
    assert r_xlsx.status_code == 400
    assert "Unsupported file type" in r_xlsx.json()["detail"]

    r_empty = client.post(
        "/materials/ingest",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"kind": "question_paper"},
    )
    assert r_empty.status_code == 400
    assert "empty" in r_empty.json()["detail"].lower()

    r_invalid_kind = client.post(
        "/materials/ingest",
        files={"file": ("doc.txt", b"Q1. Hello", "text/plain")},
        data={"kind": "unsupported_kind"},
    )
    assert r_invalid_kind.status_code == 422


def test_faculty_material_approval_and_scoped_retrieval():
    """Stage 4 Test: Faculty approves lecture notes and PYQs, which indexes them
    into the knowledge repository and makes them retrievable strictly for that assessment."""
    repo = get_knowledge_repository()
    assessment_id = "cs301_final_exam"

    # Step 1: Upload and approve lecture notes
    approval_payload = {
        "assessment_id": assessment_id,
        "document_type": "notes",
        "filename": "CS301_Graph_Algorithms.pdf",
        "content": (
            "Dijkstra's algorithm finds single-source shortest path for graphs with non-negative edge weights. "
            "It maintains a priority queue of vertices ordered by tentative distances. "
            "Edge relaxation updates distances if a shorter path is found."
        ),
        "subject": "CS301",
    }
    r_app = client.post("/materials/approve", json=approval_payload)
    assert r_app.status_code == 200, r_app.text
    app_data = r_app.json()
    assert app_data["status"] == "approved"
    assert app_data["indexed_chunks"] >= 1

    # Step 2: Check status endpoint
    r_stat = client.get(f"/materials/status/{assessment_id}")
    assert r_stat.status_code == 200
    stat_data = r_stat.json()
    assert stat_data["total_approved_knowledge_objects"] >= 1
    assert "notes" in stat_data["materials_by_type"]

    # Step 3: Retrieve grounding sources for matching assessment
    sources = retrieve_grounding_sources(
        assessment_id=assessment_id,
        question_id="Q1",
        student_answer="The algorithm uses edge relaxation and a priority queue to update shortest distances.",
        repository=repo,
    )
    assert len(sources) >= 1
    assert any("priority queue" in s.excerpt.lower() for s in sources)
    assert any(s.source_file == "CS301_Graph_Algorithms.pdf" for s in sources)

    # Step 4: Cross-course isolation check: different assessment cannot retrieve this evidence
    other_sources = retrieve_grounding_sources(
        assessment_id="different_course_101",
        question_id="Q1",
        student_answer="The algorithm uses edge relaxation and a priority queue.",
        repository=repo,
    )
    assert len(other_sources) == 0, "Cross-course leakage detected! Materials from other assessments must not be retrieved."


def test_orchestration_succeeds_even_when_optional_materials_are_empty():
    """Verify evaluation never fails if optional notes/PYQ retrieval returns no results."""
    rubric = {
        "criteria": [
            {"name": "Concept", "max_score": 5.0},
            {"name": "Accuracy", "max_score": 5.0},
        ]
    }
    res = evaluate_with_orchestrator(
        assessment_id="brand_new_empty_assessment",
        question_id="Q1",
        question="What is encapsulation in OOP?",
        student_answer="Bundling data with the methods that operate on that data.",
        model_answer="Encapsulation is bundling data and methods that operate on it, restricting direct access.",
        rubric=rubric,
    )
    assert res["score"] > 0
    assert res["max_score"] == 10.0
    assert "evaluation_trace" in res
    assert res["evaluation_trace"]["trace_id"].startswith("tr-")
