from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestedQuestionOut(BaseModel):
    question_id: str
    question_text: str
    model_answer: str
    max_score: Optional[float] = Field(default=None, description="Best-effort extraction; None if not confidently found.")
    source: str
    mapping_confidence: float = Field(ge=0, le=1)
    detected: bool


class RubricCriterionOut(BaseModel):
    code: Optional[str] = None
    description: str
    max_marks: float
    partial_credit: bool = False


class MaterialIngestionResponse(BaseModel):
    questions: List[IngestedQuestionOut] = Field(default_factory=list)
    raw_text_preview: str = ""
    extraction_engine: str = "text"
    document_type: str = "question_paper"
    rubric_criteria: Optional[Dict[str, List[RubricCriterionOut]]] = None
    sections_preview: Optional[List[str]] = None
    status: str = "extracted"
    filename: Optional[str] = None
    size_bytes: Optional[int] = None


class MaterialApprovalRequest(BaseModel):
    assessment_id: str
    document_type: str = Field(description='"question_paper", "model_answer", "rubric", "notes", "lecture_notes", "reference", or "pyq"')
    filename: str
    content: Optional[str] = None
    questions: Optional[List[IngestedQuestionOut]] = None
    rubric_criteria: Optional[Dict[str, List[RubricCriterionOut]]] = None
    subject: str = "General"
    actor: str = "Faculty"


class MaterialApprovalResponse(BaseModel):
    status: str = "approved"
    assessment_id: str
    document_type: str
    indexed_chunks: int = 0
    knowledge_ids: List[str] = Field(default_factory=list)
    message: str = ""

