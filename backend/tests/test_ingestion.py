"""Tests for faculty material ingestion (B1/B2/B3).

Uses genuinely-generated documents, not mocked text: a real committed PDF
fixture (backend/tests/fixtures/sample_model_answers.pdf, produced once via
macOS's cupsfilter so the test suite itself stays portable/CI-safe) and a
DOCX authored in pure Python at test time via python-docx.
"""

import io
from pathlib import Path

import docx
import pytest

from backend.app.services import ingestion_service
from backend.app.services.ingestion_service import UnsupportedDocumentError, ingest_document

FIXTURES = Path(__file__).parent / "fixtures"


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Real PDF ingestion
# ---------------------------------------------------------------------------


def test_real_pdf_model_answer_ingestion():
    content = (FIXTURES / "sample_model_answers.pdf").read_bytes()
    result = ingest_document("sample_model_answers.pdf", content, kind="model_answer")

    assert result.extraction_engine == "pdf"
    ids = [q.question_id for q in result.questions]
    assert ids == ["Q1", "Q2"]

    q1 = result.questions[0]
    assert "supervised learning" in q1.model_answer.lower()
    assert q1.question_text == ""  # model_answer kind never populates question_text
    assert q1.max_score == 10.0  # extracted from "[10 marks]"
    assert q1.source == "sample_model_answers.pdf"
    assert q1.mapping_confidence == 1.0  # a real "Q1." marker was found

    q2 = result.questions[1]
    assert q2.max_score == 8.0  # extracted from "(8 marks)"


def test_real_pdf_question_paper_ingestion_populates_question_text():
    content = (FIXTURES / "sample_model_answers.pdf").read_bytes()
    result = ingest_document("paper.pdf", content, kind="question_paper")

    q1 = result.questions[0]
    assert q1.question_text != ""
    assert q1.model_answer == ""


# ---------------------------------------------------------------------------
# Real DOCX ingestion
# ---------------------------------------------------------------------------


def test_real_docx_ingestion():
    content = _make_docx_bytes(
        [
            "Q1. What does a hash function guarantee?",
            "A hash function deterministically maps input of any size to a fixed-size output. [5 marks]",
            "Q2. Define a Merkle tree.",
            "A Merkle tree is a binary tree of hashes used to efficiently verify data integrity. (5 marks)",
        ]
    )
    result = ingest_document("answers.docx", content, kind="model_answer")

    assert result.extraction_engine == "docx"
    assert [q.question_id for q in result.questions] == ["Q1", "Q2"]
    assert "hash function" in result.questions[0].model_answer.lower()
    assert result.questions[0].max_score == 5.0


# ---------------------------------------------------------------------------
# TXT ingestion (no extra dependency needed)
# ---------------------------------------------------------------------------


def test_txt_ingestion():
    content = b"Q1. Explain recursion.\nA function that calls itself to solve smaller instances of a problem."
    result = ingest_document("answers.txt", content, kind="model_answer")
    assert result.extraction_engine == "txt"
    assert result.questions[0].question_id == "Q1"
    assert result.questions[0].max_score is None  # no marks stated -- must not guess


# ---------------------------------------------------------------------------
# Uncertain / low-confidence mapping is preserved, not hidden
# ---------------------------------------------------------------------------


def test_unmarked_document_flagged_low_mapping_confidence():
    content = b"This document has no question markers anywhere in it at all."
    result = ingest_document("unmarked.txt", content, kind="model_answer")
    assert len(result.questions) == 1
    assert result.questions[0].mapping_confidence == 0.5  # B3: flag, don't silently trust


# ---------------------------------------------------------------------------
# Duplicate-content handling: ingestion is a stateless, deterministic
# transform (no persistence layer exists yet -- see knowledge_repository.py),
# so re-ingesting byte-identical content must be idempotent.
# ---------------------------------------------------------------------------


def test_duplicate_ingestion_is_idempotent():
    content = b"Q1. Same content twice.\nSame answer text."
    first = ingest_document("dup.txt", content, kind="model_answer")
    second = ingest_document("dup.txt", content, kind="model_answer")
    assert first.questions[0].model_answer == second.questions[0].model_answer
    assert first.questions[0].question_id == second.questions[0].question_id


# ---------------------------------------------------------------------------
# Unsupported / corrupt / empty files
# ---------------------------------------------------------------------------


def test_unsupported_extension_rejected():
    with pytest.raises(UnsupportedDocumentError, match="Unsupported file type"):
        ingest_document("answers.xlsx", b"whatever", kind="model_answer")


def test_empty_file_rejected():
    with pytest.raises(UnsupportedDocumentError, match="empty"):
        ingest_document("empty.txt", b"", kind="model_answer")


def test_corrupt_pdf_rejected():
    with pytest.raises(UnsupportedDocumentError, match="[Cc]ould not read this PDF"):
        ingest_document("corrupt.pdf", b"not actually a pdf file", kind="model_answer")


def test_corrupt_docx_rejected():
    with pytest.raises(UnsupportedDocumentError, match="[Cc]ould not read this DOCX"):
        ingest_document("corrupt.docx", b"not actually a docx file", kind="model_answer")


def test_oversized_file_rejected(monkeypatch):
    monkeypatch.setattr(ingestion_service, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(UnsupportedDocumentError, match="15 MB"):
        ingest_document("big.txt", b"more than ten bytes of content", kind="model_answer")


def test_invalid_kind_rejected():
    with pytest.raises(ValueError, match="Unknown ingestion kind"):
        ingest_document("x.txt", b"Q1. text", kind="not_a_real_kind")
