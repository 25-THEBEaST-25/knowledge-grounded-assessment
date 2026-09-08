"""Sanity tests for the documented (unimplemented) storage abstraction (B5/B6).

There is no live repository behind this -- these only confirm the dataclass
contract is well-formed and that AcademicKnowledgeRepository is a Protocol
(a documented interface, not something accidentally instantiable/claimed as
a real implementation).
"""

import typing

from backend.app.services.knowledge_repository import (
    AcademicKnowledgeRepository,
    KnowledgeMetadata,
    KnowledgeObject,
)


def test_academic_knowledge_repository_is_a_protocol_not_a_concrete_class():
    assert typing.get_origin(AcademicKnowledgeRepository) is None
    assert getattr(AcademicKnowledgeRepository, "_is_protocol", False) is True


def test_knowledge_metadata_carries_the_b5_field_list():
    meta = KnowledgeMetadata(
        subject="NLP",
        assessment_id="a-nlp-tt2",
        semester="5",
        academic_year="2026-27",
        question_id="Q3",
        subquestion_id="a",
        co="CO3",
        po="PO2",
        document_type="model_answer",
        source_file="ModelAnswers.pdf",
        page=2,
        faculty_owner="Dr. Rajesh Kumar",
        version=1,
        approval_status="pending",
    )
    assert meta.version == 1
    assert meta.approval_status == "pending"


def test_knowledge_object_wraps_metadata_and_content():
    meta = KnowledgeMetadata(
        subject="NLP", assessment_id="a1", semester="5", academic_year="2026-27", question_id="Q1"
    )
    obj = KnowledgeObject(metadata=meta, content="A dependency parser produces head-dependent relations.")
    assert obj.metadata.question_id == "Q1"
    assert "dependency parser" in obj.content
