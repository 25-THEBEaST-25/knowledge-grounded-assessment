from backend.app.services.segmentation_service import match_marker, segment_answers


def test_detects_common_markers():
    text = """Name: Student A
Q1. Photosynthesis converts light energy
into chemical energy.
Q.2) Mitochondria is the powerhouse of the cell.
Question 3: Osmosis is diffusion of water.
Ans 4 - DNA carries genetic information.
5. Enzymes are biological catalysts.
"""
    result = segment_answers(text)
    assert result.question_ids == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert result.segments[0].text.startswith("Name: Student A\nPhotosynthesis")
    assert "into chemical energy." in result.segments[0].text
    assert result.segments[1].text == "Mitochondria is the powerhouse of the cell."
    assert result.segments[4].text == "Enzymes are biological catalysts."
    assert result.unassigned_preamble == "Name: Student A"


def test_tolerates_ocr_noise_in_markers():
    assert match_marker("Ql. answer") == ("Q1", "answer")
    assert match_marker("QI0) answer") == ("Q10", "answer")
    assert match_marker("0.2 answer") == ("Q2", "answer")
    assert match_marker("Q 3 : answer") == ("Q3", "answer")


def test_sub_questions():
    text = "Q1(a) first part\nQ1 (b) second part\n2(a) other"
    result = segment_answers(text)
    assert result.question_ids == ["Q1a", "Q1b", "Q2a"]


def test_plain_sentences_are_not_markers():
    assert match_marker("A cell is the basic unit of life.") is None
    assert match_marker("In 1990 the theory was revised.") is None
    assert match_marker("Aim of life") is None
    assert match_marker("Also, 2 moles react.") is None


def test_no_markers_gives_single_segment():
    result = segment_answers("just one long answer\nspanning lines", expected_question_ids=["Q7"])
    assert len(result.segments) == 1
    assert result.segments[0].question_id == "Q7"
    assert result.segments[0].detected is True
    assert result.segments[0].text == "just one long answer\nspanning lines"


def test_expected_ids_fill_missing_and_order():
    text = "Q2. answer two\nQ1. answer one"
    result = segment_answers(text, expected_question_ids=["Q1", "Q2", "Q3"])
    assert result.question_ids == ["Q1", "Q2", "Q3"]
    q3 = result.segments[2]
    assert q3.text == "" and q3.detected is False


def test_duplicate_markers_are_merged():
    text = "Q1. part one\nQ2. two\nQ1. continued"
    result = segment_answers(text)
    assert result.question_ids == ["Q1", "Q2"]
    assert result.segments[0].text == "part one\ncontinued"


def test_empty_text():
    result = segment_answers("")
    assert result.segments == []


def test_mapping_confidence_full_for_real_marker():
    result = segment_answers("Q1. a real answer")
    assert result.segments[0].mapping_confidence == 1.0


def test_mapping_confidence_low_for_undetected_expected_question():
    result = segment_answers("Q1. answer one", expected_question_ids=["Q1", "Q2"])
    q2 = next(s for s in result.segments if s.question_id == "Q2")
    assert q2.detected is False
    assert q2.mapping_confidence == 0.0


def test_mapping_confidence_medium_for_unmarked_fallback():
    """No markers anywhere in the text -- the whole thing is assigned to the
    first expected question as a guess, not a confident detection."""
    result = segment_answers("just a wall of text with no question markers", expected_question_ids=["Q1"])
    assert result.segments[0].detected is True
    assert result.segments[0].mapping_confidence == 0.5


def test_mapping_confidence_takes_minimum_on_merge():
    """Merging must not let a confident fragment silently upgrade an unsure
    one -- the merged segment keeps the lower (more conservative) of the two."""
    from backend.app.services.segmentation_service import Segment, _merge_duplicates

    confident = Segment(question_id="Q1", text="part one", start_line=0, end_line=0, mapping_confidence=1.0)
    unsure = Segment(question_id="Q1", text="continued", start_line=2, end_line=2, mapping_confidence=0.5)
    merged = _merge_duplicates([confident, unsure])
    assert len(merged) == 1
    assert merged[0].mapping_confidence == 0.5
