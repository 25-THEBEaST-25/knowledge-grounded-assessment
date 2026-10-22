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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.services.segmentation_service import segment_answers

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}
SUPPORTED_KINDS = {
    "question_paper",
    "model_answer",
    "rubric",
    "reference",
    "notes",
    "lecture_notes",
    "pyq",
}


class UnsupportedDocumentError(ValueError):
    """Raised for an unsupported file type, or a corrupt/unreadable/empty document."""


@dataclass
class IngestedQuestion:
    question_id: str
    question_text: str  # populated for kind="question_paper" or "pyq"; blank for "model_answer"
    model_answer: str  # populated for kind="model_answer"; blank for "question_paper"
    max_score: Optional[float]
    source: str
    mapping_confidence: float  # from Segment.mapping_confidence -- see segmentation_service
    detected: bool


@dataclass
class IngestionResult:
    questions: List[IngestedQuestion]
    raw_text_preview: str  # first 2000 chars, so faculty can sanity-check extraction quality
    extraction_engine: str
    rubric_criteria: Optional[Dict[str, List[Dict[str, Any]]]] = None
    document_type: str = "question_paper"
    sections_preview: Optional[List[str]] = None


def _extract_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
        if text.strip():
            return text
    except Exception:
        pass

    # Fallback to OCR for scanned / image-only PDFs
    try:
        from backend.app.services.ocr_service import extract_text
        from backend.app.services.pdf_utils import render_pdf_pages

        pdf_pages = render_pdf_pages(content)
        ocr_text = "\n".join(extract_text(p).text for p in pdf_pages)
        if ocr_text.strip():
            return ocr_text
    except Exception as exc:
        raise UnsupportedDocumentError(
            "Could not read this PDF -- it may be corrupt, password-protected, or scanned "
            "images without a text layer."
        ) from exc

    raise UnsupportedDocumentError(
        "Could not read this PDF -- it may be corrupt, password-protected, or scanned "
        "images without a text layer (image-only PDFs are not OCR'd by this endpoint)."
    )


def _extract_docx(content: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(content))
    except Exception as exc:
        raise UnsupportedDocumentError("Could not read this DOCX file -- it may be corrupt.") from exc
    return "\n".join(p.text for p in document.paragraphs)


def _extract_image(content: bytes) -> str:
    try:
        from backend.app.services.ocr_service import extract_text

        res = extract_text(content)
        if res.text.strip():
            return res.text
    except Exception as exc:
        raise UnsupportedDocumentError(f"Could not read image document: {exc}") from exc
    raise UnsupportedDocumentError("No text found in image document.")


_EXTRACTORS = {
    ".txt": _extract_txt,
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".png": _extract_image,
    ".jpg": _extract_image,
    ".jpeg": _extract_image,
}


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


_MARKS_RE = re.compile(
    r"[\[\(]\s*(?P<m1>\d{1,3})\s*(?:marks?|m)\s*[\]\)]"
    r"|(?:max(?:imum)?\s*)?marks?\s*[:\-]?\s*(?P<m2>\d{1,3})\b",
    re.I,
)

_CRIT_MARKS = re.compile(
    r"[\[\(]\s*(\d+(?:\.\d+)?)\s*(?:marks?|m)?\s*[\]\)]|(\d+(?:\.\d+)?)\s*(?:marks?|m)\b|[-–:]\s*(\d+(?:\.\d+)?)\s*$",
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


def parse_rubric_text(text: str) -> Dict[str, List[Dict[str, Any]]]:
    """Parse rubric criteria per question header (e.g. 'Q1' / 'Question 1')."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for seg in segment_answers(text).segments:
        crits = []
        for line in seg.text.splitlines():
            clean = line.strip(" \t•*-–")
            partial = bool(re.search(r"(?i)\(partial credit\)", clean))
            clean = re.sub(r"(?i)\s*\(partial credit\)", "", clean)
            mt = _CRIT_MARKS.search(clean)
            if not mt or not clean:
                continue
            marks = float(next(g for g in mt.groups() if g))
            if marks <= 0:
                continue
            desc = clean[: mt.start()].strip(" :-–()[]") or clean
            if len(desc) < 3 or re.fullmatch(r"(?i)(total|max(imum)?)[^a-z]*marks?.*", desc):
                continue
            crits.append({"description": desc, "max_marks": marks, "partial_credit": partial})
        if crits:
            out[seg.question_id] = crits
    return out


def ingest_document(filename: str, content: bytes, kind: str) -> IngestionResult:
    """Ingest academic resources: question papers, model answers, rubrics,
    notes, reference material, or previous year question papers (PYQs)."""
    if kind not in SUPPORTED_KINDS:
        raise ValueError(f"Unknown ingestion kind: {kind!r}")

    text = extract_text_from_document(filename, content)
    segmentation = segment_answers(text)

    rubric_criteria = None
    sections_preview = None

    if kind in ("question_paper", "pyq"):
        questions = [
            IngestedQuestion(
                question_id=seg.question_id,
                question_text=seg.text,
                model_answer="",
                max_score=_extract_marks(seg.marker_line or "") or _extract_marks(seg.text),
                source=filename,
                mapping_confidence=seg.mapping_confidence,
                detected=seg.detected,
            )
            for seg in segmentation.segments
            if seg.text.strip()
        ]
    elif kind == "model_answer":
        questions = [
            IngestedQuestion(
                question_id=seg.question_id,
                question_text="",
                model_answer=seg.text,
                max_score=_extract_marks(seg.marker_line or "") or _extract_marks(seg.text),
                source=filename,
                mapping_confidence=seg.mapping_confidence,
                detected=seg.detected,
            )
            for seg in segmentation.segments
            if seg.text.strip()
        ]
    elif kind == "rubric":
        rubric_criteria = parse_rubric_text(text)
        questions = [
            IngestedQuestion(
                question_id=seg.question_id,
                question_text="",
                model_answer=seg.text,
                max_score=sum(c["max_marks"] for c in rubric_criteria.get(seg.question_id, []))
                or _extract_marks(seg.text),
                source=filename,
                mapping_confidence=seg.mapping_confidence,
                detected=seg.detected,
            )
            for seg in segmentation.segments
            if seg.text.strip()
        ]
    elif kind in ("reference", "notes", "lecture_notes"):
        raw_sections = [p.strip() for p in text.split("\n\n") if p.strip()]
        sections_preview = raw_sections[:10]
        questions = [
            IngestedQuestion(
                question_id=f"Sec{idx + 1}",
                question_text="",
                model_answer=sec[:300],
                max_score=None,
                source=filename,
                mapping_confidence=1.0,
                detected=True,
            )
            for idx, sec in enumerate(raw_sections[:5])
        ]
    else:
        questions = []

    return IngestionResult(
        questions=questions,
        raw_text_preview=text[:2000],
        extraction_engine=_extension(filename).lstrip("."),
        rubric_criteria=rubric_criteria,
        document_type=kind,
        sections_preview=sections_preview,
    )

