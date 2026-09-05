from backend.app.services.ocr_service import OCRLine, build_result, order_lines


def _line(text, x0, y0, x1, y1, conf=0.9):
    return OCRLine(text=text, confidence=conf, bbox=[x0, y0, x1, y1])


def test_tall_overlapping_handwriting_boxes_keep_line_order():
    # bboxes taken from a real cursive sample: boxes are ~45px tall with ~26px
    # line pitch, so consecutive lines overlap vertically.
    lines = [
        _line("line3", 21, 201, 534, 242),
        _line("line1", 24, 153, 532, 192),
        _line("line2", 24, 178, 526, 217),
    ]
    assert [l.text for l in order_lines(lines)] == ["line1", "line2", "line3"]


def test_side_by_side_boxes_are_read_left_to_right():
    lines = [_line("right", 300, 10, 400, 30), _line("left", 10, 12, 100, 31), _line("below", 10, 50, 200, 70)]
    assert [l.text for l in order_lines(lines)] == ["left", "right", "below"]


def test_build_result_joins_lines_and_averages_confidence():
    r = build_result([_line("a", 0, 0, 10, 10, 0.8), _line("b", 0, 20, 10, 30, 0.6)], "x")
    assert r.text == "a\nb"
    assert r.mean_confidence == 0.7
    assert r.engine == "x"
    assert build_result([], "x").is_empty
