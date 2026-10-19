
from typing import List, Optional

from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    question: str
    student_answer: str
    model_answer: str
    rubric: dict
    assessment_id: str = "demo-assessment"
    question_id: str = "demo-question"


class EvaluationResponse(BaseModel):
    score: float = Field(default=0)
    max_score: float = Field(default=0)

    concept_score: float = Field(default=0)
    accuracy_score: float = Field(default=0)
    precision_score: float = Field(default=0)
    technical_terminology_score: float = Field(default=0)

    strengths: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    feedback: str = ""

    confidence: float = Field(default=0, ge=0, le=1)
    needs_review: bool = False

    criteria_breakdown: Optional[dict] = None
    evaluation_trace: Optional[dict] = None
