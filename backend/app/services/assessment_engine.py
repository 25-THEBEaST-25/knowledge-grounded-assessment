"""Deterministic mark calculation. The LLM only supplies per-criterion evidence
statuses; every mark is computed here from the faculty-approved rubric."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

FULL = "SATISFIED"
PARTIAL = "PARTIAL"
ZERO = {"MISSING", "INCORRECT"}
VALID_STATUSES = {FULL, PARTIAL, "MISSING", "INCORRECT", "UNCERTAIN"}


@dataclass
class CriterionSpec:
    id: str
    code: str
    max_marks: float
    partial_credit: bool = False  # PARTIAL earns half marks only if the rubric allows it


@dataclass
class EvidenceItem:
    code: str
    status: str
    confidence: float = 0.0
    evidence_id: Optional[str] = None


@dataclass
class CriterionAward:
    criterion_id: str
    code: str
    awarded: float
    max_marks: float
    confidence: float
    evidence_id: Optional[str]
    flags: List[str] = field(default_factory=list)


@dataclass
class EngineResult:
    awards: List[CriterionAward]
    total: float
    max_total: float
    flags: List[str]


def _award(spec: CriterionSpec, status: str) -> tuple[float, List[str]]:
    if status == FULL:
        return spec.max_marks, []
    if status == PARTIAL:
        if spec.partial_credit:
            return round(spec.max_marks / 2, 4), []
        return 0.0, ["PARTIAL_NOT_ALLOWED_BY_RUBRIC"]
    if status in ZERO:
        return 0.0, []
    return 0.0, ["UNCERTAIN_EVIDENCE"]  # UNCERTAIN / anything unrecognised earns nothing and is flagged


def score_response(criteria: Sequence[CriterionSpec], evidence: Sequence[EvidenceItem],
                   subquestion_max: Optional[float] = None) -> EngineResult:
    flags: List[str] = []
    if not criteria:
        return EngineResult([], 0.0, subquestion_max or 0.0, ["RUBRIC_MISSING"])

    by_code: Dict[str, List[EvidenceItem]] = {}
    for ev in evidence:
        by_code.setdefault(ev.code, []).append(ev)
    known = {c.code for c in criteria}
    if set(by_code) - known:
        flags.append("EVIDENCE_FOR_UNKNOWN_CRITERION")  # ignored, never awarded

    awards: List[CriterionAward] = []
    for spec in criteria:
        items = by_code.get(spec.code, [])
        cflags: List[str] = []
        if not items:
            awards.append(CriterionAward(spec.id, spec.code, 0.0, spec.max_marks, 0.0, None, ["MISSING_EVIDENCE"]))
            flags.append("MISSING_EVIDENCE")
            continue
        scored = [(_award(spec, i.status), i) for i in items]
        if len({i.status for i in items}) > 1:
            cflags.append("CONFLICTING_EVIDENCE")  # duplicates may never add up: take the most conservative
            pick = min(scored, key=lambda s: s[0][0])
        else:
            pick = max(scored, key=lambda s: s[1].confidence)
        (marks, extra), item = pick
        cflags += extra
        flags += cflags
        awards.append(CriterionAward(spec.id, spec.code, marks, spec.max_marks, item.confidence, item.evidence_id, cflags))

    rubric_total = round(sum(c.max_marks for c in criteria), 4)
    cap = rubric_total
    if subquestion_max is not None and subquestion_max < rubric_total:
        cap = subquestion_max
        flags.append("RUBRIC_TOTAL_EXCEEDS_QUESTION_MAX")
    elif subquestion_max is not None and subquestion_max > rubric_total:
        flags.append("RUBRIC_TOTAL_BELOW_QUESTION_MAX")
    total = min(round(sum(a.awarded for a in awards), 4), cap)
    return EngineResult(awards, total, cap, sorted(set(flags)))
