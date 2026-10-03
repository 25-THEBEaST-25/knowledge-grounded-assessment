"""JSON views over the relational trace (submission -> response -> evidence -> marks -> review)."""
from typing import Dict, List

from backend.app.db import models as m
from backend.app.services import policy, review_service


def response_view(db, r: m.StudentResponse) -> Dict:
    sq = db.get(m.SubQuestion, r.subquestion_id)
    marks = review_service.response_marks(db, r)
    plan = db.query(m.EvaluationPlan).filter_by(response_id=r.id, superseded=False).first()
    scores = {s.criterion_id: s for s in db.query(m.CriterionScore).filter_by(response_id=r.id)}
    ev_by_id = {e.id: e for e in db.query(m.Evidence).join(m.EvaluationResult).filter(m.EvaluationResult.response_id == r.id)}
    result = (db.query(m.EvaluationResult).filter_by(response_id=r.id).order_by(m.EvaluationResult.created_at.desc()).first())
    criteria = []
    for c in (sq.rubric.criteria if sq.rubric else []):
        s = scores.get(c.id)
        e = ev_by_id.get(s.evidence_id) if s and s.evidence_id else None
        criteria.append({"code": c.code, "description": c.description, "max_marks": c.max_marks,
                         "awarded": s.awarded if s else None, "flags": s.flags if s else [],
                         "evidence": ({"status": e.status, "text": e.evidence_text, "confidence": e.confidence,
                                       "source_refs": e.source_refs} if e else None)})
    reviews = db.query(m.HumanReview).filter_by(response_id=r.id).order_by(m.HumanReview.created_at).all()
    band = ("HIGH_CANDIDATE" if marks["overall_confidence"] >= policy.high_threshold()
            else "REVIEW_RECOMMENDED" if marks["overall_confidence"] >= policy.review_threshold() else "REVIEW_MANDATORY")
    return {
        "id": str(r.id), "subquestion": sq.full_id, "question_text": sq.text,
        "model_answer": sq.model_answer.text if sq.model_answer else None,
        "student_text": r.text, "detected": r.detected, "extraction_edited": r.extraction_edited,
        "region_ref": r.region_ref, "needs_review": r.needs_review, "review_reasons": r.review_reasons,
        "ocr_confidence": r.ocr_confidence, "mapping_confidence": r.mapping_confidence,
        "evaluator_confidence": marks["evaluator_confidence"], "overall_confidence": marks["overall_confidence"],
        "confidence_band": band, "ai_marks": marks["ai_marks"], "max_marks": marks["max_marks"],
        "final_marks": marks["final_marks"], "reviewed": marks["reviewed"], "criteria": criteria,
        "plan": ({"id": str(plan.id), "type": plan.response_type, "status": plan.status,
                  "tasks": [{"evaluator": t.evaluator, "status": t.status, "reason": t.reason, "attempts": t.attempts,
                             "error": t.error, "started_at": t.started_at, "finished_at": t.finished_at} for t in plan.tasks]}
                 if plan else None),
        "retrieval": ({"status": result.retrieval_status, "sources": result.retrieved_chunks} if result else None),
        "reviews": [{"reviewer": h.reviewer, "action": h.action, "ai_marks": h.ai_marks, "final_marks": h.final_marks,
                     "comment": h.comment, "at": h.created_at} for h in reviews],
    }


def submission_view(db, sub: m.Submission, include_responses: bool = True) -> Dict:
    st = db.get(m.Student, sub.student_id)
    res = db.query(m.AssessmentResult).filter_by(submission_id=sub.id).first()
    out = {"id": str(sub.id), "assessment_id": str(sub.assessment_id), "student": {"roll_no": st.roll_no, "name": st.name},
           "filename": sub.filename, "status": sub.status, "error": sub.error, "ocr_confidence": sub.ocr_confidence,
           "result": ({"ai_total": res.ai_total, "final_total": res.final_total, "max_total": res.max_total, "status": res.status,
                       "overall_confidence": res.overall_confidence, "review_required": res.review_required,
                       "flags": res.flags, "published": res.published} if res else None)}
    if include_responses:
        rs = db.query(m.StudentResponse).filter_by(submission_id=sub.id).all()
        out["responses"] = sorted((response_view(db, r) for r in rs), key=lambda x: x["subquestion"])
    return out


def dashboard(db, assessment: m.Assessment) -> Dict:
    subs = db.query(m.Submission).filter_by(assessment_id=assessment.id).all()
    sq_rows = []
    for q in db.query(m.Question).filter_by(assessment_id=assessment.id):
        sq_rows += q.subquestions
    by_status: Dict[str, int] = {}
    for s in subs:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    progress: Dict[str, Dict] = {sq.full_id: {"responses": 0, "evaluated": 0, "reviewed": 0, "needs_review": 0} for sq in sq_rows}
    queue: List[Dict] = []
    totals = []
    for s in subs:
        st = db.get(m.Student, s.student_id)
        res = db.query(m.AssessmentResult).filter_by(submission_id=s.id).first()
        if res:
            totals.append({"submission_id": str(s.id), "roll_no": st.roll_no, "name": st.name, "ai_total": res.ai_total,
                           "final_total": res.final_total, "max_total": res.max_total, "status": res.status, "published": res.published})
        for r in db.query(m.StudentResponse).filter_by(submission_id=s.id):
            sq = db.get(m.SubQuestion, r.subquestion_id)
            p = progress.setdefault(sq.full_id, {"responses": 0, "evaluated": 0, "reviewed": 0, "needs_review": 0})
            p["responses"] += 1
            plan = db.query(m.EvaluationPlan).filter_by(response_id=r.id, superseded=False).first()
            p["evaluated"] += int(bool(plan and plan.status == "DONE"))
            reviewed = db.query(m.HumanReview).filter_by(response_id=r.id).count() > 0
            p["reviewed"] += int(reviewed)
            if r.needs_review or not reviewed:
                p["needs_review"] += int(not reviewed)
                if not reviewed and plan is not None:
                    queue.append({"response_id": str(r.id), "submission_id": str(s.id), "roll_no": st.roll_no,
                                  "subquestion": sq.full_id, "reasons": r.review_reasons})
    docs = [{"kind": d.kind, "filename": d.filename, "approved": d.approved, "index_status": d.index_status, "version": d.version}
            for d in db.query(m.Document).filter_by(assessment_id=assessment.id)]
    return {"assessment": {"id": str(assessment.id), "title": assessment.title, "status": assessment.status,
                           "is_demo": assessment.is_demo, "subject": assessment.subject.name},
            "documents": docs, "submissions_by_status": by_status, "question_progress": progress,
            "review_queue": queue, "results": totals}
