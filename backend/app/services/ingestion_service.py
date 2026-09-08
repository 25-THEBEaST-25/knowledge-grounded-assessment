"""Faculty material ingestion (B1/B2): turn an uploaded question-paper or
model-answer document into structured, question-wise content faculty can
review and edit, instead of manually typing every question and model answer.

Pipeline:
    uploaded document -> file validation -> text extraction
    -> question detection/segmentation (reuses segmentation_service's
       existing Q1/Q.1/Question 1/... detector, already proven against
       handwritten OCR text -- a second parser is not needed)
    -> best-effort marks extraction -> structured, faculty-reviewable result

This is a stateless transform, not a persistence layer. The faculty-approved
result is stored via the existing frontend local-assessment mechanism for
this milestone (see knowledge_repository.py for the documented future
integration point, per B5/B6 -- there is no live database or vector store
behind this).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import List, Optional

from backend.app.services.segmentation_service import segment_answers

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


class UnsupportedDocumentError(ValueError):
    """Raised for an unsupported file type, or a corrupt/unreadable/empty document."""


@dataclass
class IngestedQuestion:
    question_id: str
    question_text: str  # populated for kind="question_paper"; blank for kind="model_answer"
    model_answer: str  # populated for kind="model_answer"; blank for kind="question_paper"
    max_score: Optional[float]
    source: str
    mapping_confidence: float  # from Segment.mapping_confidence -- see segmentation_service
    detected: bool


@dataclass
class IngestionResult:
    questions: List[IngestedQuestion]
    raw_text_preview: str  # first 2000 chars, so faculty can sanity-check extraction quality
    extraction_engine: str


def _extract_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise UnsupportedDocumentError(
            "Could not read this PDF -- it may be corrupt, password-protected, or scanned "
            "images without a text layer (image-only PDFs are not OCR'd by this endpoint)."
        ) from exc
    return "\n".join(pages)


def _extract_docx(content: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(content))
    except Exception as exc:
        raise UnsupportedDocumentError("Could not read this DOCX file -- it may be corrupt.") from exc
    return "\n".join(p.text for p in document.paragraphs)


_EXTRACTORS = {".txt": _extract_txt, ".pdf": _extract_pdf, ".docx": _extract_docx}


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx >= 0 else ""


def extract_text_from_document(filename: str, content: bytes) -> str:
    if not content:
        raise UnsupportedDocumentError("Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise UnsupportedDocumentError("File exceeds the 15 MB upload limit.")
    ext = _extension(filename)
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise UnsupportedDocumentError(
            f"Unsupported file type '{ext or filename}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )
    text = extractor(content)
    if not text.strip():
        raise UnsupportedDocumentError("No extractable text was found in this document.")
    return text


# Best-effort "[10 marks]" / "(5 marks)" / "Marks: 10" / "Max Marks - 10"
# detector. Deliberately conservative: returns None (never a guessed number)
# when nothing unambiguous is found, so faculty fills it in during review
# rather than the system inventing a mark value.
_MARKS_RE = re.compile(
    r"[\[\(]\s*(?P<m1>\d{1,3})\s*(?:marks?|m)\s*[\]\)]"
    r"|(?:max(?:imum)?\s*)?marks?\s*[:\-]?\s*(?P<m2>\d{1,3})\b",
    re.I,
)


def _extract_marks(text: str) -> Optional[float]:
    match = _MARKS_RE.search(text)
    if not match:
        return None
    raw = match.group("m1") or match.group("m2")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def ingest_document(filename: str, content: bytes, kind: str) -> IngestionResult:
    """``kind`` is ``"question_paper"`` or ``"model_answer"`` -- determines
    which field of ``IngestedQuestion`` the segmented text populates. Both
    kinds go through the identical extraction/segmentation pipeline; only
    the destination field differs, so a faculty member's question-paper and
    model-answer uploads can later be aligned purely by ``question_id``
    (B3's primary alignment strategy)."""
    if kind not in ("question_paper", "model_answer"):
        raise ValueError(f"Unknown ingestion kind: {kind!r}")

    text = extract_text_from_document(filename, content)
    segmentation = segment_answers(text)

    questions = [
        IngestedQuestion(
            question_id=seg.question_id,
            question_text=seg.text if kind == "question_paper" else "",
            model_answer=seg.text if kind == "model_answer" else "",
            max_score=_extract_marks(seg.marker_line or "") or _extract_marks(seg.text),
            source=filename,
            mapping_confidence=seg.mapping_confidence,
            detected=seg.detected,
        )
        for seg in segmentation.segments
        if seg.text.strip()
    ]

    return IngestionResult(
        questions=questions,
        raw_text_preview=text[:2000],
        extraction_engine=_extension(filename).lstrip("."),
    )
