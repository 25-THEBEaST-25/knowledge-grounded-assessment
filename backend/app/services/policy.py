"""Confidence/review policy. Thresholds are PROVISIONAL engineering defaults
(configurable via env), not calibrated probabilities -- they need validating
against faculty-labelled examples. Model-reported confidence is a hint only."""
import os
from dataclasses import dataclass, field
from typing import List


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def high_threshold() -> float:
    return _f("CONF_HIGH", 0.90)


def review_threshold() -> float:
    return _f("CONF_REVIEW_RECOMMENDED", 0.75)


def ocr_flag_threshold() -> float:
    return _f("CONF_OCR_FLAG", 0.80)


@dataclass
class ConfidenceAssessment:
    overall: float
    band: str  # HIGH_CANDIDATE | REVIEW_RECOMMENDED | REVIEW_MANDATORY
    mandatory_review: bool
    reasons: List[str] = field(default_factory=list)


def assess_confidence(*, ocr: float, mapping: float, evaluator: float, hard_flags: List[str]) -> ConfidenceAssessment:
    """Overall = min of the three (conservative: one weak link caps the result).
    Any hard flag forces mandatory review regardless of the numbers. Even a
    HIGH_CANDIDATE is only a candidate: publication is a separate faculty act."""
    overall = round(max(0.0, min(1.0, min(ocr, mapping, evaluator))), 4)
    reasons = list(hard_flags)
    if ocr < ocr_flag_threshold():
        reasons.append("LOW_OCR_CONFIDENCE")
    if mapping < review_threshold():
        reasons.append("UNCERTAIN_QUESTION_MAPPING")
    if overall >= high_threshold():
        band = "HIGH_CANDIDATE"
    elif overall >= review_threshold():
        band = "REVIEW_RECOMMENDED"
    else:
        band = "REVIEW_MANDATORY"
    mandatory = bool(reasons) or band == "REVIEW_MANDATORY"
    if band == "REVIEW_MANDATORY" and "LOW_OVERALL_CONFIDENCE" not in reasons:
        reasons.append("LOW_OVERALL_CONFIDENCE")
    return ConfidenceAssessment(overall, band, mandatory, sorted(set(reasons)))
