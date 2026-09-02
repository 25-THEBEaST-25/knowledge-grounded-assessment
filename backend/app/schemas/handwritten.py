from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.evaluation import EvaluationResponse


class OCRLineOut(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    bbox: List[int] = Field(description="[x_min, y_min, x_max, y_max]")


class OCRResponse(BaseModel):
    extracted_text: str
    lines: List[OCRLineOut]
    mean_confidence: float = Field(ge=0, le=1)
    engine: str


class SegmentRequest(BaseModel):
    text: str
    expected_question_ids: Optional[List[str]] = None


class SegmentOut(BaseModel):
    question_id: str
    text: str
    start_line: int
    end_line: int
    marker_line: Optional[str] = None
    detected: bool = True


class SegmentResponse(BaseModel):
    segments: List[SegmentOut]
    unassigned_preamble: str = ""


class QuestionSpec(BaseModel):
    """One question of the paper with its grading material."""

    question_id: str = Field(examples=["Q1"])
    question: str
    model_answer: str
    rubric: dict
    max_score: Optional[float] = Field(
        default=None,
        gt=0,
        description="Used when the answer is missing; otherwise the evaluator's max_score is used.",
    )


class QuestionResult(EvaluationResponse):
    question_id: str
    student_answer: str
    answer_detected: bool
    ocr_confidence: float = Field(ge=0, le=1)
    combined_confidence: float = Field(ge=0, le=1)
    needs_review: bool


class HandwrittenEvaluationResponse(BaseModel):
    extracted_text: str
    ocr_confidence: float = Field(ge=0, le=1)
    ocr_engine: str
    segments: List[SegmentOut]
    results: List[QuestionResult]
    total_score: float = Field(ge=0)
    total_max_score: float = Field(ge=0)
    overall_confidence: float = Field(ge=0, le=1)
    needs_review: bool
