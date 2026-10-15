"""Tests for Faculty-Approved Scoped Knowledge Retrieval (Requirement C).

Verifies strict assessment scoping, integration with existing ingestion service,
and generation of auditable SourceReference objects.
"""

from backend.app.services.knowledge_repository import InMemoryKnowledgeRepository
from backend.app.services.retrieval_service import (
    index_material_document,
    register_approved_question_material,
    retrieve_grounding_sources,
)


def test_retrieval_is_strictly_scoped_to_assessment():
    repo = InMemoryKnowledgeRepository()

    # Ingest materials for Assessment A
    register_approved_question_material(
        assessment_id="assessment_A",
        question_id="Q1",
        model_answer="Assessment A model answer: TCP is connection-oriented.",
        rubric={"max_score": 10},
        source_file="Assessment_A_Doc.txt",
        repository=repo,
    )

    # Ingest materials for Assessment B
    register_approved_question_material(
        assessment_id="assessment_B",
        question_id="Q1",
        model_answer="Assessment B model answer: UDP is connectionless.",
        rubric={"max_score": 10},
        source_file="Assessment_B_Doc.txt",
        repository=repo,
    )

    # Retrieval for Assessment A must NEVER return Assessment B's material
    sources_a = retrieve_grounding_sources(
        assessment_id="assessment_A",
        question_id="Q1",
        student_answer="TCP establishes connections.",
        repository=repo,
    )

    assert len(sources_a) >= 1
    assert all("Assessment A" in s.excerpt or s.source_file == "Assessment_A_Doc.txt" for s in sources_a)
    assert not any("UDP is connectionless" in s.excerpt for s in sources_a)


def test_index_material_document_reuses_ingestion_service():
    repo = InMemoryKnowledgeRepository()
    txt_content = (
        "Q1. What is an operating system?\n"
        "An operating system manages computer hardware and software resources.\n\n"
        "Q2. What is virtual memory?\n"
        "Virtual memory uses secondary storage to simulate additional RAM.\n"
    ).encode("utf-8")

    questions = index_material_document(
        assessment_id="os_midterm",
        filename="os_notes.txt",
        content=txt_content,
        kind="model_answer",
        subject="OS",
        repository=repo,
    )

    assert len(questions) == 2
    assert questions[0].question_id.upper() == "Q1"

    # Query repository for Q1
    refs = retrieve_grounding_sources(
        assessment_id="os_midterm",
        question_id="Q1",
        student_answer="The OS controls hardware resources.",
        repository=repo,
    )

    assert len(refs) >= 1
    assert refs[0].source_file == "os_notes.txt"
    assert "hardware and software resources" in refs[0].excerpt
    assert refs[0].relevance_score == 1.0


def test_retrieval_prioritizes_exact_question_match():
    repo = InMemoryKnowledgeRepository()
    register_approved_question_material(
        assessment_id="db_exam",
        question_id="Q1",
        model_answer="Primary key uniquely identifies each record in a table.",
        rubric={"max_score": 5},
        source_file="DB_Answers.pdf",
        repository=repo,
    )
    register_approved_question_material(
        assessment_id="db_exam",
        question_id="Q2",
        model_answer="Foreign key references a primary key in another table.",
        rubric={"max_score": 5},
        source_file="DB_Answers.pdf",
        repository=repo,
    )

    refs_q1 = retrieve_grounding_sources(
        assessment_id="db_exam",
        question_id="Q1",
        student_answer="It uniquely identifies a row in a table.",
        repository=repo,
    )

    assert len(refs_q1) >= 1
    assert refs_q1[0].question_id.upper() == "Q1"
    assert "Primary key" in refs_q1[0].excerpt
