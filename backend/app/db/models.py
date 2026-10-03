"""Relational model for the assessment lifecycle.

Traceability chain:
submission -> student_response -> evaluation_plan/task/result -> evidence
-> criterion_score -> human_review -> assessment_result (+ audit_logs).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class _Row:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def fk(target: str, **kw):
    return mapped_column(Uuid, ForeignKey(target, ondelete=kw.pop("ondelete", "CASCADE")), **kw)


class User(_Row, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # faculty | student


class Student(_Row, Base):
    __tablename__ = "students"
    roll_no: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[uuid.UUID | None] = fk("users.id", ondelete="SET NULL", nullable=True)


class Subject(_Row, Base):
    __tablename__ = "subjects"
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class Assessment(_Row, Base):
    __tablename__ = "assessments"
    subject_id: Mapped[uuid.UUID] = fk("subjects.id", ondelete="RESTRICT", index=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")  # DRAFT|MATERIALS_APPROVED|OPEN|CLOSED
    created_by: Mapped[str] = mapped_column(String(200), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    subject = relationship("Subject")


class Document(_Row, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("assessment_id", "kind", "sha256"),)
    assessment_id: Mapped[uuid.UUID] = fk("assessments.id", index=True)
    kind: Mapped[str] = mapped_column(String(30))  # question_paper|model_answer|rubric|reference
    filename: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(1000))  # file bytes live in storage, not the DB
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    index_status: Mapped[str] = mapped_column(String(30), default="NOT_INDEXED")  # RAG indexing state


class Question(_Row, Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("assessment_id", "qid"),)
    assessment_id: Mapped[uuid.UUID] = fk("assessments.id", index=True)
    qid: Mapped[str] = mapped_column(String(20))  # e.g. Q1
    text: Mapped[str] = mapped_column(Text, default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    subquestions = relationship("SubQuestion", back_populates="question", cascade="all, delete-orphan")


class SubQuestion(_Row, Base):
    """Gradable unit. A question with no parts has exactly one with key ''."""
    __tablename__ = "subquestions"
    __table_args__ = (UniqueConstraint("question_id", "key"), Index("ix_subq_full", "full_id"))
    question_id: Mapped[uuid.UUID] = fk("questions.id", index=True)
    key: Mapped[str] = mapped_column(String(10), default="")  # a, b, ... or ''
    full_id: Mapped[str] = mapped_column(String(30))  # normalized: Q1a / Q1
    text: Mapped[str] = mapped_column(Text, default="")
    max_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    question = relationship("Question", back_populates="subquestions")
    model_answer = relationship("ModelAnswer", uselist=False, cascade="all, delete-orphan")
    rubric = relationship("Rubric", uselist=False, cascade="all, delete-orphan")


class ModelAnswer(_Row, Base):
    __tablename__ = "model_answers"
    subquestion_id: Mapped[uuid.UUID] = fk("subquestions.id", unique=True)
    text: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_document_id: Mapped[uuid.UUID | None] = fk("documents.id", ondelete="SET NULL", nullable=True)


class Rubric(_Row, Base):
    """Absent row == rubric MISSING. Never auto-invented as faculty-approved."""
    __tablename__ = "rubrics"
    subquestion_id: Mapped[uuid.UUID] = fk("subquestions.id", unique=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    source_document_id: Mapped[uuid.UUID | None] = fk("documents.id", ondelete="SET NULL", nullable=True)
    criteria = relationship("RubricCriterion", back_populates="rubric", cascade="all, delete-orphan",
                            order_by="RubricCriterion.position")


class RubricCriterion(_Row, Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (UniqueConstraint("rubric_id", "code"),)
    rubric_id: Mapped[uuid.UUID] = fk("rubrics.id", index=True)
    code: Mapped[str] = mapped_column(String(20))  # C1, C2...
    position: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text)
    max_marks: Mapped[float] = mapped_column(Float)
    expected_concepts: Mapped[list] = mapped_column(JsonType, default=list)
    partial_credit: Mapped[bool] = mapped_column(Boolean, default=False)  # may PARTIAL earn half? only if True
    rubric = relationship("Rubric", back_populates="criteria")


class Submission(_Row, Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id", "file_sha256"),)
    assessment_id: Mapped[uuid.UUID] = fk("assessments.id", index=True)
    student_id: Mapped[uuid.UUID] = fk("students.id", index=True)
    filename: Mapped[str] = mapped_column(String(500))
    file_sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="UPLOADED")
    # UPLOADED|PROCESSING|EXTRACTED|EVALUATING|EVALUATED|NEEDS_REVIEW|FINAL|FAILED
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class StudentResponse(_Row, Base):
    __tablename__ = "student_responses"
    __table_args__ = (UniqueConstraint("submission_id", "subquestion_id"),)
    submission_id: Mapped[uuid.UUID] = fk("submissions.id", index=True)
    subquestion_id: Mapped[uuid.UUID] = fk("subquestions.id", ondelete="RESTRICT", index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    detected: Mapped[bool] = mapped_column(Boolean, default=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    mapping_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    region_ref: Mapped[dict] = mapped_column(JsonType, default=dict)  # {page, bbox}
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reasons: Mapped[list] = mapped_column(JsonType, default=list)
    extraction_edited: Mapped[bool] = mapped_column(Boolean, default=False)  # faculty corrected OCR text


class EvaluationPlan(_Row, Base):
    __tablename__ = "evaluation_plans"
    response_id: Mapped[uuid.UUID] = fk("student_responses.id", index=True)
    response_type: Mapped[str] = mapped_column(String(10))  # TEXT|MATH|CODE|VISUAL|MCQ|MIXED
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|RUNNING|DONE|FAILED
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    tasks = relationship("EvaluationTask", back_populates="plan", cascade="all, delete-orphan")


class EvaluationTask(_Row, Base):
    __tablename__ = "evaluation_tasks"
    plan_id: Mapped[uuid.UUID] = fk("evaluation_plans.id", index=True)
    evaluator: Mapped[str] = mapped_column(String(20))  # TEXT now; MATH/CODE/VISUAL pending
    reason: Mapped[str] = mapped_column(Text)
    input_ref: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|RUNNING|DONE|FAILED|NOT_IMPLEMENTED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan = relationship("EvaluationPlan", back_populates="tasks")


class EvaluationResult(_Row, Base):
    __tablename__ = "evaluation_results"
    task_id: Mapped[uuid.UUID] = fk("evaluation_tasks.id", index=True)
    response_id: Mapped[uuid.UUID] = fk("student_responses.id", index=True)
    raw_output: Mapped[dict] = mapped_column(JsonType, default=dict)
    model: Mapped[str] = mapped_column(String(100), default="")
    retrieval_status: Mapped[str] = mapped_column(String(30), default="NOT_ATTEMPTED")  # USED|UNAVAILABLE|NO_MATCH|NOT_ATTEMPTED
    retrieved_chunks: Mapped[list] = mapped_column(JsonType, default=list)  # source refs shown to faculty


class Evidence(_Row, Base):
    __tablename__ = "evidence"
    result_id: Mapped[uuid.UUID] = fk("evaluation_results.id", index=True)
    criterion_id: Mapped[uuid.UUID] = fk("rubric_criteria.id", ondelete="RESTRICT")
    status: Mapped[str] = mapped_column(String(20))  # SATISFIED|PARTIAL|MISSING|INCORRECT|UNCERTAIN
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_refs: Mapped[list] = mapped_column(JsonType, default=list)
    region_ref: Mapped[dict] = mapped_column(JsonType, default=dict)


class CriterionScore(_Row, Base):
    __tablename__ = "criterion_scores"
    __table_args__ = (UniqueConstraint("response_id", "criterion_id"),)  # blocks double-awarding
    response_id: Mapped[uuid.UUID] = fk("student_responses.id", index=True)
    criterion_id: Mapped[uuid.UUID] = fk("rubric_criteria.id", ondelete="RESTRICT")
    evidence_id: Mapped[uuid.UUID | None] = fk("evidence.id", ondelete="SET NULL", nullable=True)
    awarded: Mapped[float] = mapped_column(Float)
    max_marks: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    flags: Mapped[list] = mapped_column(JsonType, default=list)


class HumanReview(_Row, Base):
    """Append-only. The AI result is never overwritten; latest review wins for final marks."""
    __tablename__ = "human_reviews"
    response_id: Mapped[uuid.UUID] = fk("student_responses.id", index=True)
    reviewer: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(10))  # ACCEPT|MODIFY|REJECT
    ai_marks: Mapped[float] = mapped_column(Float)
    final_marks: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(Text, default="")


class AssessmentResult(_Row, Base):
    __tablename__ = "assessment_results"
    submission_id: Mapped[uuid.UUID] = fk("submissions.id", unique=True)
    ai_total: Mapped[float] = mapped_column(Float, default=0.0)
    final_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_total: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="AI_PROPOSED")  # AI_PROPOSED|UNDER_REVIEW|FINAL
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    flags: Mapped[list] = mapped_column(JsonType, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=False)  # visible to student only after faculty finalize


class AuditLog(_Row, Base):
    __tablename__ = "audit_logs"
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
