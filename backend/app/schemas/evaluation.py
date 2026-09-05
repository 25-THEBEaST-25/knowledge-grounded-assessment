from typing import List

from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    question: str
    student_answer: str
    model_answer: str
    rubric: dict


class EvaluationResponse(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)

    concept_score: float = Field(ge=0)
    accuracy_score: float = Field(ge=0)
    precision_score: float = Field(ge=0)
    technical_terminology_score: float = Field(ge=0)

    strengths: List[str]
    missing_concepts: List[str]
    feedback: str

    confidence: float = Field(ge=0, le=1)