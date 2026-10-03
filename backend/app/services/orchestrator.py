"""Orchestrator: classifies the response, writes a persisted EvaluationPlan,
runs only the needed evaluators, then hands EVIDENCE to the deterministic
Assessment Engine. It never assigns marks itself."""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.db import models as m
from backend.app.services import audit, policy, rag_service, text_evaluator
from backend.app.services.assessment_engine import CriterionSpec, EvidenceItem, score_response
from backend.app.services.evaluation_service import GeminiUnavailableError

logger = logging.getLogger(__name__)

IMPLEMENTED = {"TEXT"}
_CODE_RE = re.compile(r"(\bdef \w+\(|\bint main\(|#include|\bpublic static|;\s*$|\{\s*$|\bfor \(|\bwhile \(|=>|\bimport \w+)", re.M)
_MCQ_RE = re.compile(r"(?m)^\s*\(?[A-Da-d][\).]\s+\S.*\n\s*\(?[B-Eb-e][\).]\s+\S")
_VISUAL_RE = re.compile(r"\b(draw|sketch|diagram|figure|label the|plot|circuit|flowchart)\b", re.I)
_MATH_RE = re.compile(r"(\d\s*[=+\-*/^]\s*\d|\\frac|\bsolve\b|\bcalculate\b|\bcompute\b|\bderive\b|∫|∑|√)", re.I)


def classify_response(question_text: str, answer_text: str) -> tuple[str, List[str]]:
    """Deterministic rules only (no LLM). Returns (type, reasons). Mixed => several signals."""
    sig: Dict[str, str] = {}
    if _MCQ_RE.search(question_text or ""):
        sig["MCQ"] = "question lists lettered options"
    if _CODE_RE.search(answer_text or ""):
        sig["CODE"] = "answer contains code-like syntax"
    if _VISUAL_RE.search(question_text or ""):
        sig["VISUAL"] = "question asks for a diagram/drawing"
    if len(_MATH_RE.findall(answer_text or "")) >= 2 or _MATH_RE.search(question_text or ""):
        sig["MATH"] = "numeric/mathematical working detected"
    if not sig:
        return "TEXT", ["no code/math/visual/MCQ signals; conceptual text answer"]
    if len(sig) == 1:
        return next(iter(sig)), list(sig.values())
    return "MIXED", [f"{k}: {v}" for k, v in sig.items()]


def _now():
    return datetime.now(timezone.utc)


def create_plan(db: Session, resp: m.StudentResponse, sq: m.SubQuestion) -> m.EvaluationPlan:
    for old in db.query(m.EvaluationPlan).filter_by(response_id=resp.id, superseded=False):
        old.superseded = True
    rtype, reasons = classify_response(sq.text, resp.text)
    plan = m.EvaluationPlan(response_id=resp.id, response_type=rtype, status="PENDING")
    db.add(plan)
    db.flush()
    needed = (_needed_for_mixed(reasons) | {"TEXT"}) if rtype == "MIXED" else {rtype}  # conceptual part always attempted
    for ev in sorted(needed):
        impl = ev in IMPLEMENTED
        db.add(m.EvaluationTask(
            plan_id=plan.id, evaluator=ev,
            reason="; ".join(reasons) if impl else f"{ev} evaluator is not implemented yet; requires faculty marking. ({'; '.join(reasons)})",
            input_ref={"response_id": str(resp.id), "subquestion": sq.full_id},
            status="PENDING" if impl else "NOT_IMPLEMENTED"))
    db.flush()
    return plan


def _needed_for_mixed(reasons: List[str]) -> set:
    return {r.split(":")[0] for r in reasons if r.split(":")[0] in {"MATH", "CODE", "VISUAL", "MCQ"}}


def evaluate_response(db: Session, response_id, *, llm: Optional[text_evaluator.LLM] = None, force: bool = False,
                      actor: str = "system") -> Dict:
    """Plan + run + score one response. Idempotent unless force=True: a response whose
    current plan already finished is returned as-is (no re-run, no double marks).
    Caller commits."""
    resp = db.get(m.StudentResponse, response_id)
    sq = db.get(m.SubQuestion, resp.subquestion_id)
    sub = db.get(m.Submission, resp.submission_id)
    current = db.query(m.EvaluationPlan).filter_by(response_id=resp.id, superseded=False).first()
    if current and current.status == "DONE" and not force:
        return {"status": "ALREADY_EVALUATED", "plan_id": str(current.id)}

    hard_flags: List[str] = []
    rubric = sq.rubric
    ma = sq.model_answer
    if not (rubric and rubric.approved and rubric.criteria):
        hard_flags.append("RUBRIC_MISSING")
    if not (ma and ma.approved):
        hard_flags.append("MODEL_ANSWER_NOT_APPROVED")
    if not resp.detected or not resp.text.strip():
        hard_flags.append("ANSWER_NOT_FOUND")

    plan = create_plan(db, resp, sq)
    audit.log(db, actor, "plan.created", "evaluation_plan", plan.id, {"type": plan.response_type})

    if "RUBRIC_MISSING" in hard_flags or "MODEL_ANSWER_NOT_APPROVED" in hard_flags or "ANSWER_NOT_FOUND" in hard_flags:
        plan.status = "FAILED"
        for t in plan.tasks:
            if t.status == "PENDING":
                t.status, t.error = "FAILED", "Blocked: " + ", ".join(hard_flags)
        _finalize(db, resp, sq, plan, [], hard_flags)
        return {"status": "BLOCKED", "flags": hard_flags, "plan_id": str(plan.id)}

    plan.status = "RUNNING"
    evidence_items: List[EvidenceItem] = []
    for task in [t for t in plan.tasks if t.status == "PENDING"]:
        evidence_items += _run_text_task(db, task, resp, sq, sub, llm)
    if any(t.status == "NOT_IMPLEMENTED" for t in plan.tasks):
        hard_flags.append("EVALUATOR_NOT_IMPLEMENTED")
    if any(t.status == "FAILED" for t in plan.tasks):
        hard_flags.append("EVALUATOR_FAILED")
    plan.status = "FAILED" if "EVALUATOR_FAILED" in hard_flags else "DONE"
    _finalize(db, resp, sq, plan, evidence_items, hard_flags)
    return {"status": plan.status, "plan_id": str(plan.id), "flags": hard_flags}


def _run_text_task(db, task: m.EvaluationTask, resp, sq, sub, llm) -> List[EvidenceItem]:
    task.status, task.attempts, task.started_at = "RUNNING", task.attempts + 1, _now()
    assessment_id = str(sub.assessment_id)
    retrieval = rag_service.retrieve(rag_service.get_rag(), assessment_id, sq.full_id, f"{sq.text}\n{resp.text}"[:2000])
    criteria = [{"code": c.code, "description": c.description, "max_marks": c.max_marks,
                 "expected_concepts": c.expected_concepts or [c.description]} for c in sq.rubric.criteria]
    inp = text_evaluator.EvalInput(question=sq.text, student_answer=resp.text, model_answer=sq.model_answer.text,
                                   criteria=criteria, context=retrieval.chunks, ocr_confidence=resp.ocr_confidence)
    try:
        out, diag = text_evaluator.evaluate(inp, llm)
    except (text_evaluator.EvaluatorOutputError, GeminiUnavailableError) as exc:
        task.status, task.error, task.finished_at = "FAILED", str(exc)[:500], _now()
        return []
    result = m.EvaluationResult(task_id=task.id, response_id=resp.id, raw_output=out.model_dump() | diag,
                                model="gemini", retrieval_status=retrieval.status,
                                retrieved_chunks=[{k: c[k] for k in ("ref", "point_id", "source", "doc_type", "scope", "document_id", "score")}
                                                  for c in retrieval.chunks])
    db.add(result)
    db.flush()
    by_code = {c.code: c for c in sq.rubric.criteria}
    items: List[EvidenceItem] = []
    for ce in out.criteria:
        ev = m.Evidence(result_id=result.id, criterion_id=by_code[ce.code].id, status=ce.status,
                        evidence_text=ce.evidence, confidence=ce.confidence, source_refs=ce.source_refs,
                        region_ref=resp.region_ref or {})
        db.add(ev)
        db.flush()
        items.append(EvidenceItem(ce.code, ce.status, ce.confidence, str(ev.id)))
    task.status, task.finished_at, task.error = "DONE", _now(), None
    return items


def _finalize(db, resp, sq, plan, evidence_items, hard_flags: List[str]) -> None:
    """Deterministic scoring + persistence, replacing (never adding to) earlier awards."""
    criteria = [CriterionSpec(str(c.id), c.code, c.max_marks, c.partial_credit)
                for c in (sq.rubric.criteria if sq.rubric and sq.rubric.approved else [])]
    res = score_response(criteria, evidence_items, sq.max_marks)
    db.query(m.CriterionScore).filter_by(response_id=resp.id).delete()
    for a in res.awards:
        db.add(m.CriterionScore(response_id=resp.id, criterion_id=uuid.UUID(a.criterion_id),
                                evidence_id=uuid.UUID(a.evidence_id) if a.evidence_id else None,
                                awarded=a.awarded, max_marks=a.max_marks, confidence=a.confidence, flags=a.flags))
    flags = sorted(set(hard_flags) | set(res.flags))
    ev_conf = (sum(i.confidence for i in evidence_items) / len(evidence_items)) if evidence_items else 0.0
    conf = policy.assess_confidence(ocr=resp.ocr_confidence, mapping=resp.mapping_confidence, evaluator=ev_conf,
                                    hard_flags=flags + (["RESPONSE_FLAGGED_AT_EXTRACTION"] if resp.needs_review else []))
    resp.needs_review = conf.mandatory_review or conf.band != "HIGH_CANDIDATE"
    resp.review_reasons = conf.reasons or ([f"BAND_{conf.band}"] if conf.band != "HIGH_CANDIDATE" else [])
    audit.log(db, "system", "response.scored", "student_response", resp.id,
              {"ai_total": res.total, "max": res.max_total, "flags": flags, "confidence": conf.overall, "band": conf.band})
    db.flush()
    from backend.app.services.review_service import recompute_submission_result
    recompute_submission_result(db, resp.submission_id)
