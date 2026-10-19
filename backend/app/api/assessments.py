import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api import auth
from backend.app.db import models as m
from backend.app.db.session import get_db, new_session
from backend.app.services import materials_service as mat
from backend.app.services import read_models, review_service, storage, submission_service as subs
from backend.app.services.pdf_utils import render_pdf_pages

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Assessment"])


def _u(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise HTTPException(404, "Not found")


def _a(db: Session, assessment_id: str) -> m.Assessment:
    a = db.get(m.Assessment, _u(assessment_id))
    if a is None:
        raise HTTPException(404, "Assessment not found")
    return a


def _sub(db: Session, submission_id: str) -> m.Submission:
    s = db.get(m.Submission, _u(submission_id))
    if s is None:
        raise HTTPException(404, "Submission not found")
    return s


def _wrap(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except (mat.MaterialError, subs.SubmissionError, review_service.ReviewError) as exc:
        raise HTTPException(422, str(exc))


class AssessmentIn(BaseModel):
    subject_code: str = Field(min_length=1, max_length=50)
    subject_name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)


class CriterionIn(BaseModel):
    code: Optional[str] = None
    description: str = Field(min_length=3)
    max_marks: float = Field(gt=0)
    partial_credit: bool = False


class SubQuestionPatch(BaseModel):
    text: Optional[str] = None
    max_marks: Optional[float] = Field(default=None, gt=0)
    model_answer: Optional[str] = None
    criteria: Optional[List[CriterionIn]] = None


class TextPatch(BaseModel):
    text: str


class ReviewIn(BaseModel):
    action: str
    final_marks: Optional[float] = None
    comment: str = ""


# ---------- faculty: setup ----------
@router.post("/assessments", status_code=201)
def create_assessment(body: AssessmentIn, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    a = mat.create_assessment(db, subject_code=body.subject_code, subject_name=body.subject_name, title=body.title, actor=who.name)
    db.commit()
    return {"id": str(a.id), "status": a.status}


@router.get("/assessments")
def list_assessments(db: Session = Depends(get_db), who=Depends(auth.faculty)):
    return [{"id": str(a.id), "title": a.title, "status": a.status, "is_demo": a.is_demo, "subject": a.subject.name}
            for a in db.query(m.Assessment).order_by(m.Assessment.created_at.desc())]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    a = _a(db, assessment_id)
    return {"id": str(a.id), "title": a.title, "status": a.status, "is_demo": a.is_demo, "subject": a.subject.name,
            "items": mat.review_status(db, a.id),
            "documents": [{"id": str(d.id), "kind": d.kind, "filename": d.filename, "approved": d.approved,
                           "version": d.version, "index_status": d.index_status}
                          for d in db.query(m.Document).filter_by(assessment_id=a.id)]}


@router.post("/assessments/{assessment_id}/documents", status_code=201)
async def upload_document(assessment_id: str, kind: str = Form(...), file: UploadFile = File(...),
                          db: Session = Depends(get_db), who=Depends(auth.faculty)):
    a = _a(db, assessment_id)
    content = await file.read()
    out = _wrap(mat.add_document, db, a, kind, file.filename or "upload", content, who.name)
    db.commit()
    return out


@router.patch("/assessments/{assessment_id}/subquestions/{subquestion_id}")
def edit_subquestion(assessment_id: str, subquestion_id: str, body: SubQuestionPatch, db: Session = Depends(get_db),
                     who=Depends(auth.faculty)):
    a = _a(db, assessment_id)
    sq = db.get(m.SubQuestion, _u(subquestion_id))
    if sq is None or sq.question.assessment_id != a.id:
        raise HTTPException(404, "Subquestion not found")
    _wrap(mat.edit_subquestion, db, sq, text=body.text, max_marks=body.max_marks, model_answer=body.model_answer,
          criteria=[c.model_dump() for c in body.criteria] if body.criteria is not None else None, actor=who.name)
    a.status = "DRAFT"
    db.commit()
    return {"ok": True}


@router.post("/assessments/{assessment_id}/approve")
def approve(assessment_id: str, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    out = _wrap(mat.approve_assessment, db, _a(db, assessment_id), who.name)
    db.commit()
    return out


# ---------- submissions ----------
@router.post("/assessments/{assessment_id}/submissions", status_code=201)
async def upload_submission(assessment_id: str, roll_no: str = Form(...), student_name: str = Form(""),
                            file: UploadFile = File(...), db: Session = Depends(get_db), who=Depends(auth.faculty)):
    a = _a(db, assessment_id)
    content = await file.read()
    out = _wrap(subs.upload_submission, db, a, roll_no=roll_no, student_name=student_name,
                filename=file.filename or "upload", content=content, actor=who.name)
    db.commit()
    return out


def _bg_process_and_evaluate(submission_id, actor: str, do_eval: bool, force: bool) -> None:
    try:
        with new_session() as db:
            subs.process_submission(db, submission_id, force=force, actor=actor)
            db.commit()
            status = db.get(m.Submission, submission_id).status
        if do_eval and status == "EXTRACTED":
            subs.evaluate_submission(new_session, submission_id, force=force, actor=actor)
    except Exception:
        logger.exception("Background processing failed for %s", submission_id)
        with new_session() as db:
            s = db.get(m.Submission, submission_id)
            if s:
                s.status, s.error = "FAILED", "Processing failed unexpectedly; retry."
                db.commit()


@router.post("/submissions/{submission_id}/process", status_code=202)
def process(submission_id: str, bg: BackgroundTasks, evaluate: bool = Query(True), force: bool = Query(False),
            sync: bool = Query(False), db: Session = Depends(get_db), who=Depends(auth.faculty)):
    sub = _sub(db, submission_id)
    if sync:
        _bg_process_and_evaluate(sub.id, who.name, evaluate, force)
        db.expire_all()
        return read_models.submission_view(db, _sub(db, submission_id), include_responses=False)
    if sub.status in ("PROCESSING", "EVALUATING") and not force:
        return {"status": sub.status, "note": "already running"}
    bg.add_task(_bg_process_and_evaluate, sub.id, who.name, evaluate, force)
    return {"status": "ACCEPTED", "note": "poll GET /submissions/{id} for status"}


@router.post("/submissions/{submission_id}/evaluate", status_code=202)
def evaluate(submission_id: str, bg: BackgroundTasks, force: bool = Query(False), sync: bool = Query(False),
             db: Session = Depends(get_db), who=Depends(auth.faculty)):
    sub = _sub(db, submission_id)
    if sync:
        return _wrap(subs.evaluate_submission, new_session, sub.id, force=force, actor=who.name)
    bg.add_task(subs.evaluate_submission, new_session, sub.id, force=force, actor=who.name)
    return {"status": "ACCEPTED"}


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: str, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    return read_models.submission_view(db, _sub(db, submission_id))


@router.get("/submissions/{submission_id}/page/{page}")
def get_page(submission_id: str, page: int, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    sub = _sub(db, submission_id)
    content = storage.read(sub.storage_path)
    if sub.filename.lower().endswith(".pdf"):
        pages = render_pdf_pages(content, scale=1.5)
        if not 1 <= page <= len(pages):
            raise HTTPException(404, "Page not found")
        return Response(pages[page - 1], media_type="image/png")
    if page != 1:
        raise HTTPException(404, "Page not found")
    return Response(content, media_type="image/png" if sub.filename.lower().endswith(".png") else "image/jpeg")


@router.patch("/responses/{response_id}/text")
def correct_text(response_id: str, body: TextPatch, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    _wrap(subs.correct_response_text, db, _u(response_id), body.text, who.name)
    db.commit()
    return {"ok": True, "note": "re-run evaluation for this submission with force=true"}


@router.post("/responses/{response_id}/review")
def review(response_id: str, body: ReviewIn, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    rid = _u(response_id)
    if db.get(m.StudentResponse, rid) is None:
        raise HTTPException(404, "Response not found")
    _wrap(review_service.record_review, db, rid, reviewer=who.name, action=body.action,
          final_marks=body.final_marks, comment=body.comment)
    db.commit()
    return read_models.response_view(db, db.get(m.StudentResponse, rid))


@router.post("/submissions/{submission_id}/publish")
def publish(submission_id: str, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    _wrap(review_service.publish_result, db, _u(submission_id), reviewer=who.name)
    db.commit()
    return {"published": True}


@router.get("/assessments/{assessment_id}/dashboard")
def get_dashboard(assessment_id: str, db: Session = Depends(get_db), who=Depends(auth.faculty)):
    return read_models.dashboard(db, _a(db, assessment_id))


@router.get("/assessments/{assessment_id}/audit")
def get_audit(assessment_id: str, limit: int = Query(200, le=1000), db: Session = Depends(get_db), who=Depends(auth.faculty)):
    _a(db, assessment_id)
    rows = db.query(m.AuditLog).order_by(m.AuditLog.created_at.desc()).limit(limit).all()
    return [{"at": r.created_at, "actor": r.actor, "action": r.action, "entity": r.entity, "entity_id": r.entity_id, "payload": r.payload} for r in rows]


# ---------- student ----------
@router.get("/students/me/results")
def my_results(db: Session = Depends(get_db), who=Depends(auth.student)):
    """Only PUBLISHED (faculty-finalised) results, with final marks -- never AI-proposed marks."""
    st = db.query(m.Student).filter_by(roll_no=who.name).first()
    if st is None:
        return []
    out = []
    for s in db.query(m.Submission).filter_by(student_id=st.id):
        res = db.query(m.AssessmentResult).filter_by(submission_id=s.id).first()
        if not res or not res.published:
            continue
        a = db.get(m.Assessment, s.assessment_id)
        qs = []
        for r in db.query(m.StudentResponse).filter_by(submission_id=s.id):
            v = read_models.response_view(db, r)
            qs.append({"subquestion": v["subquestion"], "question_text": v["question_text"], "final_marks": v["final_marks"],
                       "max_marks": v["max_marks"], "comment": (v["reviews"][-1]["comment"] if v["reviews"] else ""),
                       "criteria": [{"description": c["description"], "max_marks": c["max_marks"]} for c in v["criteria"]]})
        out.append({"assessment": a.title, "final_total": res.final_total, "max_total": res.max_total, "questions": sorted(qs, key=lambda x: x["subquestion"])})
    return out
