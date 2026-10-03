"""Human review (OSM-style) + submission roll-up. AI results are never overwritten:
reviews are append-only and the latest one defines the final marks."""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.db import models as m
from backend.app.services import audit


class ReviewError(ValueError):
    pass


def response_marks(db: Session, resp: m.StudentResponse) -> Dict:
    scores = db.query(m.CriterionScore).filter_by(response_id=resp.id).all()
    sq = db.get(m.SubQuestion, resp.subquestion_id)
    max_marks = sum(s.max_marks for s in scores) if scores else (sq.max_marks or 0.0)
    if sq.max_marks is not None:
        max_marks = min(max_marks, sq.max_marks) if scores else sq.max_marks
    ai = min(round(sum(s.awarded for s in scores), 4), max_marks) if scores else 0.0
    review = (db.query(m.HumanReview).filter_by(response_id=resp.id)
              .order_by(m.HumanReview.created_at.desc(), m.HumanReview.id.desc()).first())
    conf = round(sum(s.confidence for s in scores) / len(scores), 4) if scores else 0.0
    return {"ai_marks": ai, "max_marks": max_marks, "final_marks": review.final_marks if review else None,
            "reviewed": review is not None, "evaluator_confidence": conf,
            "overall_confidence": round(min(resp.ocr_confidence, resp.mapping_confidence, conf), 4)}


def recompute_submission_result(db: Session, submission_id) -> m.AssessmentResult:
    sub = db.get(m.Submission, submission_id)
    resps = db.query(m.StudentResponse).filter_by(submission_id=submission_id).all()
    rows = [response_marks(db, r) for r in resps]
    ai_total = round(sum(r["ai_marks"] for r in rows), 4)
    max_total = round(sum(r["max_marks"] for r in rows), 4)
    all_reviewed = bool(rows) and all(r["reviewed"] for r in rows)
    some_reviewed = any(r["reviewed"] for r in rows)
    flags = sorted({f for r in resps for f in (r.review_reasons or [])})
    res = db.query(m.AssessmentResult).filter_by(submission_id=submission_id).first()
    if res is None:
        res = m.AssessmentResult(submission_id=submission_id)
        db.add(res)
    res.ai_total, res.max_total = ai_total, max_total
    res.final_total = round(sum(r["final_marks"] for r in rows), 4) if all_reviewed else None
    res.overall_confidence = min((r["overall_confidence"] for r in rows), default=0.0)
    res.status = "FINAL" if all_reviewed else ("UNDER_REVIEW" if some_reviewed else "AI_PROPOSED")
    res.review_required = not all_reviewed  # AI marks are proposals until faculty review completes
    res.flags = flags
    sub.status = "FINAL" if all_reviewed else "NEEDS_REVIEW"
    db.flush()
    return res


def record_review(db: Session, response_id, *, reviewer: str, action: str, final_marks: Optional[float],
                  comment: str = "") -> m.HumanReview:
    """One transaction (caller commits): append review + audit row + recompute totals."""
    action = action.upper()
    if action not in {"ACCEPT", "MODIFY", "REJECT"}:
        raise ReviewError("action must be ACCEPT, MODIFY or REJECT")
    resp = db.get(m.StudentResponse, response_id)
    if resp is None:
        raise ReviewError("response not found")
    marks = response_marks(db, resp)
    ai, cap = marks["ai_marks"], marks["max_marks"]
    if action == "ACCEPT":
        final = ai
    else:
        if final_marks is None and action == "MODIFY":
            raise ReviewError("final_marks is required to modify")
        final = 0.0 if final_marks is None else float(final_marks)
        if action == "MODIFY" and abs(final - ai) < 1e-9:
            raise ReviewError("modified marks equal the AI proposal; use ACCEPT")
        if action in {"MODIFY", "REJECT"} and not comment.strip():
            raise ReviewError("a comment/reason is required to modify or reject")
    if not 0 <= final <= cap + 1e-9:
        raise ReviewError(f"final_marks must be between 0 and {cap:g}")
    review = m.HumanReview(response_id=resp.id, reviewer=reviewer, action=action, ai_marks=ai,
                           final_marks=final, comment=comment.strip())
    db.add(review)
    audit.log(db, reviewer, f"review.{action.lower()}", "student_response", resp.id,
              {"ai_marks": ai, "final_marks": final, "comment": comment.strip()})
    db.flush()
    recompute_submission_result(db, resp.submission_id)
    return review


def publish_result(db: Session, submission_id, *, reviewer: str) -> m.AssessmentResult:
    res = db.query(m.AssessmentResult).filter_by(submission_id=submission_id).first()
    if res is None:
        raise ReviewError("no result to publish")
    if res.status != "FINAL":
        raise ReviewError("every question must be reviewed by faculty before publishing")
    res.published = True
    audit.log(db, reviewer, "result.published", "assessment_result", res.id, {"final_total": res.final_total})
    return res
