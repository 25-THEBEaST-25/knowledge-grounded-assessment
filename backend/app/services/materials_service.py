"""Faculty setup: create assessment, ingest question paper / model answers / rubric /
reference docs, review-edit, approve (which triggers RAG indexing)."""
import hashlib
import os
import re
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.db import models as m
from backend.app.services import audit, rag_service, storage
from backend.app.services.ingestion_service import (
    UnsupportedDocumentError, _extract_marks, _extension, extract_text_from_document,
)
from backend.app.services.segmentation_service import segment_answers

KINDS = {"question_paper", "model_answer", "rubric", "reference"}
_QID = re.compile(r"^(Q\d+)([a-z]?)$")
_CRIT_MARKS = re.compile(r"[\[\(]\s*(\d+(?:\.\d+)?)\s*(?:marks?|m)?\s*[\]\)]|(\d+(?:\.\d+)?)\s*(?:marks?|m)\b|[-–:]\s*(\d+(?:\.\d+)?)\s*$", re.I)


class MaterialError(ValueError):
    pass


def max_upload_bytes() -> int:
    return int(float(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024)


def split_qid(full: str) -> tuple[str, str]:
    mt = _QID.match(full)
    return (mt.group(1), mt.group(2)) if mt else (full, "")


def extract_material_text(filename: str, content: bytes) -> str:
    """Text-layer extraction first; OCR fallback for scanned PDFs."""
    try:
        return extract_text_from_document(filename, content)
    except UnsupportedDocumentError:
        if _extension(filename) != ".pdf":
            raise
    from backend.app.services.ocr_service import extract_text
    from backend.app.services.pdf_utils import render_pdf_pages
    try:
        pages = render_pdf_pages(content)
    except ValueError as exc:
        raise UnsupportedDocumentError(str(exc)) from exc
    text = "\n".join(extract_text(p).text for p in pages)
    if not text.strip():
        raise UnsupportedDocumentError("No text found, even with OCR.")
    return text


def parse_rubric_text(text: str) -> Dict[str, List[Dict]]:
    """Rubric format per question: one criterion per line with its marks, e.g.
    'Q1a' header then '- Defines TCP handshake (2 marks)'. Lines without marks are ignored
    (never guessed). '(partial credit)' in a line allows half marks for PARTIAL."""
    out: Dict[str, List[Dict]] = {}
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
            desc = clean[:mt.start()].strip(" :-–()[]") or clean
            if len(desc) < 3 or re.fullmatch(r"(?i)(total|max(imum)?)[^a-z]*marks?.*", desc):
                continue
            crits.append({"description": desc, "max_marks": marks, "partial_credit": partial})
        if crits:
            out[seg.question_id] = crits
    return out


def create_assessment(db: Session, *, subject_code: str, subject_name: str, title: str, actor: str,
                      is_demo: bool = False) -> m.Assessment:
    subject = db.query(m.Subject).filter_by(code=subject_code).first() or m.Subject(code=subject_code, name=subject_name)
    db.add(subject)
    db.flush()
    a = m.Assessment(subject_id=subject.id, title=title, created_by=actor, is_demo=is_demo)
    db.add(a)
    db.flush()
    audit.log(db, actor, "assessment.created", "assessment", a.id, {"title": title})
    return a


def _get_subq(db, assessment_id, full_id: str) -> m.SubQuestion:
    qid, key = split_qid(full_id)
    q = db.query(m.Question).filter_by(assessment_id=assessment_id, qid=qid).first()
    if q is None:
        q = m.Question(assessment_id=assessment_id, qid=qid)
        db.add(q)
        db.flush()
    sq = db.query(m.SubQuestion).filter_by(question_id=q.id, key=key).first()
    if sq is None:
        sq = m.SubQuestion(question_id=q.id, key=key, full_id=full_id)
        db.add(sq)
        db.flush()
    return sq


def add_document(db: Session, assessment: m.Assessment, kind: str, filename: str, content: bytes, actor: str) -> Dict:
    if kind not in KINDS:
        raise MaterialError(f"kind must be one of {sorted(KINDS)}")
    if not content:
        raise MaterialError("Uploaded file is empty.")
    if len(content) > max_upload_bytes():
        raise MaterialError("File exceeds the upload size limit.")
    sha = hashlib.sha256(content).hexdigest()
    existing = db.query(m.Document).filter_by(assessment_id=assessment.id, kind=kind, sha256=sha).first()
    if existing:  # duplicate upload: idempotent, nothing re-parsed
        return {"document_id": str(existing.id), "duplicate": True, "items": 0}
    try:
        text = extract_material_text(filename, content)
    except UnsupportedDocumentError as exc:
        raise MaterialError(str(exc)) from exc

    ver = 1 + db.query(m.Document).filter_by(assessment_id=assessment.id, kind=kind).count()
    doc = m.Document(assessment_id=assessment.id, kind=kind, filename=filename, sha256=sha, size_bytes=len(content),
                     storage_path=storage.save(f"assessments/{assessment.id}", sha, filename, content), version=ver)
    db.add(doc)
    db.flush()
    items = 0
    if kind in ("question_paper", "model_answer"):
        for seg in segment_answers(text).segments:
            if not seg.text.strip():
                continue
            sq = _get_subq(db, assessment.id, seg.question_id)
            sq.approved = False
            if kind == "question_paper":
                sq.text = seg.text.strip()
                sq.max_marks = _extract_marks(seg.marker_line or "") or _extract_marks(seg.text) or sq.max_marks
                sq.question.text = sq.question.text or ""
            else:
                if sq.model_answer is None:
                    sq.model_answer = m.ModelAnswer(text=seg.text.strip(), source_document_id=doc.id, version=ver)
                else:
                    sq.model_answer.text, sq.model_answer.approved = seg.text.strip(), False
                    sq.model_answer.version, sq.model_answer.source_document_id = ver, doc.id
            items += 1
    elif kind == "rubric":
        for full_id, crits in parse_rubric_text(text).items():
            sq = _get_subq(db, assessment.id, full_id)
            _replace_rubric(db, sq, crits, doc.id)
            items += 1
    assessment.status = "DRAFT"  # any new material needs (re-)approval
    audit.log(db, actor, "document.uploaded", "document", doc.id, {"kind": kind, "filename": filename, "items": items})
    return {"document_id": str(doc.id), "duplicate": False, "items": items}


def _replace_rubric(db, sq: m.SubQuestion, crits: List[Dict], source_doc_id=None) -> m.Rubric:
    codes = set()
    for c in crits:
        if c["max_marks"] <= 0:
            raise MaterialError("criterion marks must be positive")
    if sq.rubric is not None:
        db.delete(sq.rubric)
        db.flush()
    rub = m.Rubric(subquestion_id=sq.id, approved=False, source_document_id=source_doc_id)
    for i, c in enumerate(crits):
        code = c.get("code") or f"C{i + 1}"
        if code in codes:
            raise MaterialError(f"duplicate criterion code {code}")
        codes.add(code)
        rub.criteria.append(m.RubricCriterion(code=code, position=i, description=c["description"], max_marks=float(c["max_marks"]),
                                              expected_concepts=c.get("expected_concepts") or [c["description"]],
                                              partial_credit=bool(c.get("partial_credit", False))))
    db.add(rub)
    db.flush()
    db.refresh(sq)
    return rub


def edit_subquestion(db, sq: m.SubQuestion, *, text: Optional[str], max_marks: Optional[float],
                     model_answer: Optional[str], criteria: Optional[List[Dict]], actor: str) -> m.SubQuestion:
    if max_marks is not None and max_marks <= 0:
        raise MaterialError("max_marks must be positive")
    if text is not None:
        sq.text = text
    if max_marks is not None:
        sq.max_marks = max_marks
    if model_answer is not None:
        if sq.model_answer is None:
            sq.model_answer = m.ModelAnswer(text=model_answer)
        else:
            sq.model_answer.text, sq.model_answer.version = model_answer, sq.model_answer.version + 1
        sq.model_answer.approved = False
    if criteria is not None:
        _replace_rubric(db, sq, criteria)
    sq.approved = False
    audit.log(db, actor, "subquestion.edited", "subquestion", sq.id, {})
    return sq


def review_status(db, assessment_id) -> List[Dict]:
    rows = []
    for q in db.query(m.Question).filter_by(assessment_id=assessment_id).order_by(m.Question.qid):
        for sq in sorted(q.subquestions, key=lambda s: s.full_id):
            issues = []
            if not sq.text.strip():
                issues.append("QUESTION_TEXT_MISSING")
            if sq.model_answer is None:
                issues.append("MODEL_ANSWER_MISSING")
            if sq.rubric is None or not sq.rubric.criteria:
                issues.append("RUBRIC_MISSING")
            elif sq.max_marks is not None and abs(sum(c.max_marks for c in sq.rubric.criteria) - sq.max_marks) > 1e-9:
                issues.append("RUBRIC_TOTAL_DIFFERS_FROM_MAX_MARKS")
            rows.append({"id": str(sq.id), "full_id": sq.full_id, "text": sq.text, "max_marks": sq.max_marks,
                         "approved": sq.approved, "issues": issues,
                         "model_answer": sq.model_answer.text if sq.model_answer else None,
                         "rubric": [{"code": c.code, "description": c.description, "max_marks": c.max_marks,
                                     "partial_credit": c.partial_credit} for c in sq.rubric.criteria] if sq.rubric else None})
    return rows


def approve_assessment(db: Session, assessment: m.Assessment, actor: str) -> Dict:
    """Faculty approval. Items with a missing question/model answer are NOT approved (and so can't be
    graded); a missing rubric is reported, never invented. Then approved material is RAG-indexed."""
    rows = review_status(db, assessment.id)
    approved, blocked = 0, []
    for row in rows:
        sq = db.get(m.SubQuestion, uuid.UUID(row["id"]))
        if {"QUESTION_TEXT_MISSING", "MODEL_ANSWER_MISSING"} & set(row["issues"]):
            blocked.append({"full_id": sq.full_id, "issues": row["issues"]})
            continue
        sq.approved = True
        sq.question.approved = True
        sq.model_answer.approved = True
        if sq.rubric:
            sq.rubric.approved = True
        if "RUBRIC_MISSING" in row["issues"]:
            blocked.append({"full_id": sq.full_id, "issues": row["issues"], "note": "approved without rubric; cannot be auto-graded"})
        approved += 1
    for d in db.query(m.Document).filter_by(assessment_id=assessment.id):
        d.approved = True
    db.flush()
    if approved == 0:
        raise MaterialError("Nothing can be approved yet: upload a question paper and model answers first.")
    assessment.status = "MATERIALS_APPROVED"
    index = rag_service.index_assessment(db, assessment, rag_service.get_rag(), lambda d: extract_material_text(d.filename, storage.read(d.storage_path)))
    for d in db.query(m.Document).filter_by(assessment_id=assessment.id):
        d.index_status = index["status"]
    audit.log(db, actor, "assessment.approved", "assessment", assessment.id, {"approved": approved, "rag": index["status"]})
    return {"approved_items": approved, "issues": blocked, "rag": index}
