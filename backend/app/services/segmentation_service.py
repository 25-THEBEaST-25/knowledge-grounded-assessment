"""Question-wise segmentation of OCR'd answer-sheet text.

Pure, deterministic and dependency-free so it can be unit-tested without
PaddleOCR or an LLM. Detects question markers such as::

    Q1 / Q.1 / Q 1 / Q1) / Q1: / Question 1 / Ques 1 / Que 1
    Ans 1 / Answer 1 / Ans. 1 / A1 / A.1
    1. / 1) / (1) / 1:      (numbered lines with separator)
    Q1(a) / Q1(A) / Q1a / 1(a) / 1(A) / 1a.  -> sub-questions (e.g. "Q1a")
    Q1(i) / 1(iv)                             -> roman numeral sub-questions

OCR noise is tolerated: ``Ql``/``QI`` are read as ``Q1``, ``O`` as ``0``
inside a number, and a leading ``0.1``/``0 1`` (a mis-read ``Q.1``) is
recognised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

_NUM = r"(?P<num>[0-9OoIl]{1,3})"
# sub-question: "(a)" / "(iv)" / "(A)" anywhere after number, or a bare letter
# glued to the number and followed by a separator/end, e.g. "Q1a." / "1b)" / "Q1(a)"
_SUB = r"(?:\s*\((?P<sub>[a-hA-H]|[ivxIVX]{1,4})\)|(?P<sub2>[a-hA-H])(?=\s*[\.\):\-–—]|$))?"
_SEP = r"\s*[\.\):\-–—]?\s*"

_PATTERNS = [
    # Q1, Q.1, Q 1, Q1), Q1:, Q1(a), Question 1, Ques 1, Que 1, Qn 1
    re.compile(rf"^\s*(?:Q|Que|Ques|Question|Qn|Qu)\s*\.?\s*{_NUM}{_SUB}{_SEP}(?P<rest>.*)$", re.I),
    # Ans 1, Answer 1, Ans. 1, A1 (A1 requires a separator to avoid words like "Aim")
    re.compile(rf"^\s*(?:Ans|Answer|Ans\.)\s*\.?\s*{_NUM}{_SUB}{_SEP}(?P<rest>.*)$", re.I),
    re.compile(rf"^\s*A\s*\.?\s*{_NUM}{_SUB}\s*[\.\):\-–—]\s*(?P<rest>.*)$", re.I),
    # 1. / 1) / (1) / 1: / 1(a) / 1(A) at start of line
    re.compile(rf"^\s*\(?{_NUM}{_SUB}\)?\s*[\.\):\-–—]\s*(?P<rest>.*)$"),
    # 1(a) / 1 (b) at start of line: parenthesised sub-part acts as separator
    re.compile(rf"^\s*\(?{_NUM}\)?\s*\((?P<sub>[a-hA-H]|[ivxIVX]{{1,4}})\)\s*[\.\):\-–—]?\s*(?P<rest>.*)$"),
    # OCR mis-read of "Q.1" as "0.1" / "0 1" / "O.1" at line start
    re.compile(rf"^\s*[0Oo]\s*[\.\s]\s*(?P<num>[1-9][0-9]?){_SUB}{_SEP}(?P<rest>.*)$"),
]

_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})

_STANDALONE_NORM_RE = re.compile(
    rf"^\s*(?:Q|Que|Ques|Question|Qn|Qu|Ans|Answer|A)?\s*\.?\s*\(?{_NUM}{_SUB}\)?\s*[\.\):\-–—]?\s*$",
    re.I,
)


@dataclass
class Segment:
    question_id: str
    text: str
    start_line: int
    end_line: int
    marker_line: Optional[str] = None
    detected: bool = True


@dataclass
class SegmentationResult:
    segments: List[Segment] = field(default_factory=list)
    unassigned_preamble: str = ""

    @property
    def question_ids(self) -> List[str]:
        return [s.question_id for s in self.segments]


def normalize_question_id(raw: str, sub: Optional[str] = None) -> str:
    """Normalize question ID string into canonical form (e.g. 'Q1', 'Q1a', 'Q10').

    Handles inputs such as:
    - 'Q1', 'q1', 'Ql', 'QI', 'Q 1', 'Question 1', 'Que 1', '1.', '1)', '(1)', '1:' -> 'Q1'
    - 'Q1(a)', 'Q1(A)', 'Q1a', 'q1a', '1(a)', '1(A)', '1a.' -> 'Q1a'
    - 'Q1(iv)', '1(iv)' -> 'Q1iv'
    """
    stripped = str(raw).strip()
    if not stripped:
        return "Q1"

    # If already a number/sub directly passed
    if sub is not None or stripped.isdigit():
        num = stripped.translate(_DIGIT_FIX)
        num = str(int(num)) if num.isdigit() else num
        qid = f"Q{num}"
        if sub:
            qid += sub.lower()
        return qid

    m = _STANDALONE_NORM_RE.match(stripped)
    if m:
        num = m.group("num").translate(_DIGIT_FIX)
        if num.isdigit() and 0 < int(num) <= 500:
            num = str(int(num))
            s = m.group("sub") or m.group("sub2")
            qid = f"Q{num}"
            if s:
                qid += s.lower()
            return qid

    # Fallback marker match
    marker = match_marker(stripped)
    if marker:
        return marker[0]

    # Clean non-alphanumeric except simple prefix
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", stripped)
    if cleaned:
        if not cleaned.upper().startswith("Q"):
            cleaned = f"Q{cleaned}"
        else:
            cleaned = f"Q{cleaned[1:]}"
        return cleaned

    return "Q1"


# Alias for backwards compatibility
normalise_question_id = normalize_question_id


def match_marker(line: str):
    """Return ``(question_id, rest_of_line)`` if ``line`` starts with a marker."""
    stripped = line.strip()
    if not stripped:
        return None
    for pattern in _PATTERNS:
        m = pattern.match(stripped)
        if not m:
            continue
        num = m.group("num")
        # reject numbers that are all letters (e.g. "Ol") unless a Q prefix
        fixed = num.translate(_DIGIT_FIX)
        if not fixed.isdigit() or int(fixed) == 0 or int(fixed) > 500:
            continue
        groups = m.groupdict()
        sub = groups.get("sub") or groups.get("sub2")
        return normalize_question_id(fixed, sub), m.group("rest").strip()
    return None


def segment_answers(
    text: str,
    expected_question_ids: Optional[Sequence[str]] = None,
) -> SegmentationResult:
    """Split OCR text into per-question segments.

    - Text before the first marker is kept as ``unassigned_preamble`` and also
      prepended to the first segment.
    - If no markers are found the whole text becomes one segment with ``detected=True``.
      Its id is the first ``expected_question_ids`` entry if given, else ``Q1``.
    - If ``expected_question_ids`` is provided, any expected id that was not
      detected is appended as an empty, ``detected=False`` segment so every
      question is evaluated (and scored 0 / flagged) rather than skipped.
    """
    lines = text.splitlines()
    result = SegmentationResult()

    normalized_expected = (
        [normalize_question_id(qid) for qid in expected_question_ids]
        if expected_question_ids
        else None
    )

    current: Optional[Segment] = None
    preamble: List[str] = []
    buffers: List[List[str]] = []

    for idx, raw in enumerate(lines):
        marker = match_marker(raw)
        if marker:
            qid, rest = marker
            if current is not None:
                current.end_line = idx - 1
            current = Segment(
                question_id=qid,
                text="",
                start_line=idx,
                end_line=idx,
                marker_line=raw.strip(),
                detected=True,
            )
            result.segments.append(current)
            buffers.append([rest] if rest else [])
        elif current is None:
            preamble.append(raw)
        else:
            buffers[-1].append(raw)

    if current is not None:
        current.end_line = len(lines) - 1

    for seg, buf in zip(result.segments, buffers):
        seg.text = "\n".join(l for l in buf if l.strip()).strip()

    result.unassigned_preamble = "\n".join(l for l in preamble if l.strip()).strip()

    if not result.segments:
        # No markers detected in text
        if result.unassigned_preamble:
            qid = normalized_expected[0] if normalized_expected else "Q1"
            result.segments.append(
                Segment(
                    question_id=qid,
                    text=result.unassigned_preamble,
                    start_line=0,
                    end_line=max(0, len(lines) - 1),
                    detected=True,
                )
            )
            result.unassigned_preamble = ""
    elif result.unassigned_preamble:
        first = result.segments[0]
        first.text = (result.unassigned_preamble + "\n" + first.text).strip()

    # merge duplicate ids (e.g. answer continued later on the page)
    result.segments = _merge_duplicates(result.segments)

    if normalized_expected:
        present = {s.question_id.lower() for s in result.segments}
        for qid in normalized_expected:
            if qid.lower() not in present:
                result.segments.append(
                    Segment(
                        question_id=qid,
                        text="",
                        start_line=-1,
                        end_line=-1,
                        detected=False,
                    )
                )
                present.add(qid.lower())
        order = {q.lower(): i for i, q in enumerate(normalized_expected)}
        result.segments.sort(key=lambda s: order.get(s.question_id.lower(), len(order)))

    return result


def _merge_duplicates(segments: Iterable[Segment]) -> List[Segment]:
    merged: dict[str, Segment] = {}
    for seg in segments:
        key = seg.question_id.lower()
        if key in merged:
            prev = merged[key]
            prev.text = (prev.text + "\n" + seg.text).strip()
            prev.end_line = max(prev.end_line, seg.end_line)
            prev.detected = prev.detected or seg.detected
        else:
            merged[key] = seg
    return list(merged.values())

