"""End-to-End Assessment Integration Tests (Requirement 10 & Vertical Slice).

Tests the complete flow from normalized question answers through orchestrator,
scoped knowledge retrieval, specialized evaluators, deterministic scoring,
and full evaluation audit trace generation.
"""

from backend.app.schemas.handwritten import QuestionSpec
from backend.app.services.knowledge_repository import get_knowledge_repository
from backend.app.services.pipeline_service import evaluate_segments
from backend.app.services.retrieval_service import register_approved_question_material
from backend.app.services.segmentation_service import Segment


def test_end_to_end_assessment_flow_with_trace_and_rubric():
    repo = get_knowledge_repository()


    # 1. Register approved faculty material in repository for assessment
    assessment_id = "cs101_midterm"
    register_approved_question_material(
        assessment_id=assessment_id,
        question_id="Q1",
        model_answer="A stack is a Last-In First-Out (LIFO) data structure supporting push and pop operations.",
        rubric={
            "criteria": [
                {"name": "LIFO Concept", "max_score": 4.0},
                {"name": "Stack Operations", "max_score": 6.0},
            ]
        },
        question_text="What is a stack and what are its primary operations?",
        source_file="CS101_Syllabus.pdf",
        repository=repo,
    )

    # 2. Student answer segment
    seg = Segment(
        question_id="Q1",
        text="A stack operates on LIFO order. Push adds an item and pop removes an item.",
        start_line=0,
        end_line=2,
        detected=True,
        mapping_confidence=1.0,
    )

    # 3. Assessment specification
    spec = QuestionSpec(
        question_id="Q1",
        question="What is a stack and what are its primary operations?",
        model_answer="A stack is a Last-In First-Out (LIFO) data structure supporting push and pop operations.",
        rubric={
            "criteria": [
                {"name": "LIFO Concept", "max_score": 4.0},
                {"name": "Stack Operations", "max_score": 6.0},
            ]
        },
        max_score=10.0,
        assessment_id=assessment_id,
    )

    # 4. Evaluate via pipeline
    def dummy_evaluator(question, student_answer, model_answer, rubric, **kwargs):
        # Even if a basic evaluator returns standard scores
        return {
            "score": 9.0,
            "max_score": 10.0,
            "concept_score": 4.0,
            "accuracy_score": 5.0,
            "precision_score": 0.0,
            "technical_terminology_score": 0.0,
            "strengths": ["Understands LIFO"],
            "missing_concepts": [],
            "feedback": "Solid answer on stacks",
            "confidence": 0.95,
        }

    results = evaluate_segments(
        segments=[seg],
        questions=[spec],
        ocr_confidence=0.95,
        evaluator=dummy_evaluator,
    )

    assert len(results) == 1
    res = results[0]

    # Score clamping and values
    assert res.score <= 10.0
    assert res.max_score == 10.0
    assert res.question_id == "Q1"

    # Deterministic criteria breakdown
    assert res.criteria_breakdown is not None
    assert len(res.criteria_breakdown) == 2
    assert sum(c["max_score"] for c in res.criteria_breakdown) == 10.0
    assert all(c["awarded_score"] <= c["max_score"] for c in res.criteria_breakdown)

    # Evaluation trace & audit trail
    assert res.evaluation_trace is not None
    trace = res.evaluation_trace
    assert trace["trace_id"].startswith("tr-")
    assert "concept_text" in trace["evaluators_run"]
    assert "concept_text" in trace["routing_reasons"]

    # Scoped source references present in trace
    assert "retrieval_sources" in trace
    assert len(trace["retrieval_sources"]) >= 1
    assert any(s["source_file"] == "CS101_Syllabus.pdf" for s in trace["retrieval_sources"])
