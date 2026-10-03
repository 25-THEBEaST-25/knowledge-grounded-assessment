"""Student answer-sheet processing: validate -> OCR (existing PaddleOCR pipeline) -> segment/map
to the approved subquestions -> question-wise StudentResponse rows with OCR/mapping confidence,
page+bbox references, and review flags. Uncertain extraction is never treated as reliable."""
import hashlib
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.db import models as m
from backend.app.services import audit, orchestrator, policy, review_service, storage
from backend.app.services.materials_service import max_upload_bytes
from backend.app.services.ocr_service import InvalidImageError, OCRResult, OCRUnavailableError, extract_text
from backend.app.services.pdf_utils import render_pdf_pages
from backend.app.services.pipeline_service import build_answer_evidence
from backend.app.services.segmentation_service import normalize_question_id, segment_answers

ALLOWED = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_MAGIC = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8"}


class SubmissionError(ValueError):
    pass


def _ext(name: str) -> str:
    i = name.rfind(".")
    return name[i:].lower() if i >= 0 else ""


def upload_submission(db: Session, assessment: m.Assessment, *, roll_no: str, student_name: str, filename: str,
                      content: bytes, actor: str) -> Dict:
    if assessment.status != "MATERIALS_APPROVED":
        raise SubmissionError("Assessment materials must be approved by faculty before accepting submissions.")
    ext = _ext(filename)
    if ext not in ALLOWED:
        raise SubmissionError(f"Unsupported file type {ext or filename!r}. Allowed: {', '.join(sorted(ALLOWED))}")
    if not content:
        raise SubmissionError("Uploaded file is empty.")
    if len(content) > max_upload_bytes():
        raise SubmissionError("File exceeds the upload size limit.")
    if not content.startswith(_MAGIC[ext]):
        raise SubmissionError("File content does not match its extension.")
    if not roll_no.strip():
        raise SubmissionError("roll_no is required.")
    student = db.query(m.Student).filter_by(roll_no=roll_no.strip()).first()
    if student is None:
        student = m.Student(roll_no=roll_no.strip(), name=student_name.strip() or roll_no.strip())
        db.add(student)
        db.flush()
    sha = hashlib.sha256(content).hexdigest()
    dup = db.query(m.Submission).filter_by(assessment_id=assessment.id, student_id=student.id, file_sha256=sha).first()
    if dup:  # same student re-uploading the same file: idempotent
        return {"submission_id": str(dup.id), "duplicate": True, "status": dup.status}
    sub = m.Submission(assessment_id=assessment.id, student_id=student.id, filename=filename, file_sha256=sha,
                       storage_path=storage.save(f"submissions/{assessment.id}", sha, filename, content))
    db.add(sub)
    db.flush()
    audit.log(db, actor, "submission.uploaded", "submission", sub.id, {"roll_no": roll_no, "filename": filename})
    return {"submission_id": str(sub.id), "duplicate": False, "status": sub.status}


def _pages(sub: m.Submission) -> List[bytes]:
    content = storage.read(sub.storage_path)
    return render_pdf_pages(content) if _ext(sub.filename) == ".pdf" else [content]


def process_submission(db: Session, submission_id, *, ocr_fn: Callable[[bytes], OCRResult] = extract_text,
                       force: bool = False, actor: str = "system") -> Dict:
    """OCR + segmentation + response creation. Idempotent: an already-extracted submission is left
    alone unless force=True (and force is refused once faculty have reviewed any answer)."""
    sub = db.get(m.Submission, submission_id)
    if sub.status not in ("UPLOADED", "FAILED") and not force:
        return {"status": sub.status, "skipped": True}
    existing = db.query(m.StudentResponse).filter_by(submission_id=sub.id)
    if existing.count():
        if db.query(m.HumanReview).join(m.StudentResponse).filter(m.StudentResponse.submission_id == sub.id).count():
            raise SubmissionError("Cannot reprocess: faculty review already exists for this submission.")
        for r in existing.all():
            db.delete(r)
        db.flush()

    sub.status, sub.error = "PROCESSING", None
    subqs = [sq for q in db.query(m.Question).filter_by(assessment_id=sub.assessment_id) for sq in q.subquestions if sq.approved]
    expected = [sq.full_id for sq in subqs]
    agg: Dict[str, Dict] = {}
    page_confs: List[float] = []
    try:
        for page_no, img in enumerate(_pages(sub), start=1):
            ocr = ocr_fn(img)
            page_confs.append(ocr.mean_confidence)
            seg_result = segment_answers(ocr.text, expected_question_ids=expected)
            evidence = build_answer_evidence(seg_result.segments, ocr)
            for seg in seg_result.segments:
                key = normalize_question_id(seg.question_id)
                ev = evidence.get(key.lower())
                a = agg.setdefault(key, {"texts": [], "ocr": [], "mapping": [], "regions": [], "detected": False})
                if seg.detected and seg.text.strip():
                    a["detected"] = True
                    a["texts"].append(seg.text.strip())
                    a["ocr"].append(ev.ocr_confidence if ev else ocr.mean_confidence)
                    a["mapping"].append(seg.mapping_confidence)
                    if ev and ev.bbox:
                        a["regions"].append({"page": page_no, "bbox": ev.bbox})
    except (OCRUnavailableError, InvalidImageError, ValueError) as exc:
        sub.status, sub.error = "FAILED", str(exc)[:500]  # honest failure; retry later via process(force)
        audit.log(db, actor, "submission.failed", "submission", sub.id, {"error": sub.error})
        return {"status": "FAILED", "error": sub.error}

    for sq in subqs:
        a = agg.get(sq.full_id)
        if not a or not a["detected"]:
            db.add(m.StudentResponse(submission_id=sub.id, subquestion_id=sq.id, text="", detected=False,
                                     needs_review=True, review_reasons=["ANSWER_NOT_FOUND"]))
            continue
        ocr_c = round(sum(a["ocr"]) / len(a["ocr"]), 4)
        map_c = round(min(a["mapping"]), 4)
        reasons = []
        if ocr_c < policy.ocr_flag_threshold():
            reasons.append("LOW_OCR_CONFIDENCE")
        if map_c < policy.review_threshold():
            reasons.append("UNCERTAIN_QUESTION_MAPPING")
        db.add(m.StudentResponse(submission_id=sub.id, subquestion_id=sq.id, text="\n".join(a["texts"]), detected=True,
                                 ocr_confidence=ocr_c, mapping_confidence=map_c,
                                 region_ref={"regions": a["regions"]}, needs_review=bool(reasons), review_reasons=reasons))
    sub.ocr_confidence = round(sum(page_confs) / len(page_confs), 4) if page_confs else 0.0
    sub.status = "EXTRACTED"
    audit.log(db, actor, "submission.extracted", "submission", sub.id, {"pages": len(page_confs), "subquestions": len(subqs)})
    db.flush()
    return {"status": "EXTRACTED", "responses": len(subqs), "ocr_confidence": sub.ocr_confidence}


def correct_response_text(db: Session, response_id, text: str, actor: str) -> m.StudentResponse:
    """Review path for uncertain OCR: faculty fixes the extracted text (original OCR kept in audit log)."""
    r = db.get(m.StudentResponse, response_id)
    if r is None:
        raise SubmissionError("response not found")
    audit.log(db, actor, "response.text_corrected", "student_response", r.id, {"previous_text": r.text})
    r.text, r.extraction_edited, r.detected = text, True, bool(text.strip())
    plan = db.query(m.EvaluationPlan).filter_by(response_id=r.id, superseded=False).first()
    if plan:
        plan.status = "PENDING"  # content changed: next evaluate call must re-run
    return r


def evaluate_submission(session_factory, submission_id, *, llm=None, force: bool = False, actor: str = "system") -> Dict:
    """Evaluate every response, committing per response so one failure never loses the rest."""
    with session_factory() as db:
        sub = db.get(m.Submission, submission_id)
        if sub.status in ("UPLOADED", "PROCESSING", "FAILED"):
            raise SubmissionError("Submission has not been extracted yet.")
        sub.status = "EVALUATING"
        db.commit()
        ids = [r.id for r in db.query(m.StudentResponse).filter_by(submission_id=submission_id)]
    outcome = {"evaluated": 0, "blocked": 0, "failed": 0, "skipped": 0}
    for rid in ids:
        with session_factory() as db:
            try:
                res = orchestrator.evaluate_response(db, rid, llm=llm, force=force, actor=actor)
                db.commit()
            except Exception:
                db.rollback()
                outcome["failed"] += 1
                continue
        key = {"ALREADY_EVALUATED": "skipped", "BLOCKED": "blocked", "FAILED": "failed"}.get(res["status"], "evaluated")
        outcome[key] += 1
    with session_factory() as db:
        review_service.recompute_submission_result(db, submission_id)
        db.commit()
    return outcome
