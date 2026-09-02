"""OCR service built on PaddleOCR 3.x (``PaddleOCR.predict`` pipeline API).

The PaddleOCR engine is loaded lazily on first use so the API can boot on
machines that do not have PaddlePaddle installed; such machines get a clear
``OCRUnavailableError`` from the OCR endpoints instead of an import crash.
"""

from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Sequence

import numpy as np
from PIL import Image, UnidentifiedImageError


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class OCRUnavailableError(RuntimeError):
    """Raised when the OCR engine cannot be loaded (e.g. paddle not installed)."""


class InvalidImageError(ValueError):
    """Raised when the uploaded bytes are not a decodable image."""


@dataclass
class OCRLine:
    text: str
    confidence: float
    bbox: List[int]  # [x_min, y_min, x_max, y_max]


@dataclass
class OCRResult:
    text: str
    lines: List[OCRLine] = field(default_factory=list)
    mean_confidence: float = 0.0
    engine: str = "paddleocr"

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OCRBackend(Protocol):
    def extract(self, image_bytes: bytes) -> OCRResult: ...


def decode_image(image_bytes: bytes) -> np.ndarray:
    """Decode uploaded bytes into an RGB ``numpy`` array (H, W, 3)."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return np.asarray(img.convert("RGB"))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("Uploaded file is not a valid image.") from exc


def _bbox_from_poly(poly: Sequence[Sequence[float]]) -> List[int]:
    xs = [int(p[0]) for p in poly]
    ys = [int(p[1]) for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]


def _same_row(a: OCRLine, b: OCRLine, min_overlap: float) -> bool:
    """Two boxes are on one visual row if they overlap vertically by at least
    ``min_overlap`` of the shorter box *and* are side by side (no horizontal
    overlap). Handwriting boxes are tall and often overlap the next line, so a
    plain centre-distance test mis-orders consecutive lines."""
    v_overlap = min(a.bbox[3], b.bbox[3]) - max(a.bbox[1], b.bbox[1])
    shorter = max(1, min(a.bbox[3] - a.bbox[1], b.bbox[3] - b.bbox[1]))
    if v_overlap / shorter < min_overlap:
        return False
    h_overlap = min(a.bbox[2], b.bbox[2]) - max(a.bbox[0], b.bbox[0])
    return h_overlap <= 0


def order_lines(lines: List[OCRLine], min_overlap: float = 0.5) -> List[OCRLine]:
    """Sort OCR lines into reading order: top-to-bottom, then left-to-right."""
    if not lines:
        return []

    def centre_y(line: OCRLine) -> float:
        return (line.bbox[1] + line.bbox[3]) / 2

    by_y = sorted(lines, key=centre_y)
    rows: List[List[OCRLine]] = []
    for line in by_y:
        if rows and all(_same_row(line, other, min_overlap) for other in rows[-1]):
            rows[-1].append(line)
        else:
            rows.append([line])
    ordered: List[OCRLine] = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda l: l.bbox[0]))
    return ordered


def build_result(lines: List[OCRLine], engine: str) -> OCRResult:
    ordered = order_lines(lines)
    text = "\n".join(l.text for l in ordered)
    mean_conf = float(np.mean([l.confidence for l in ordered])) if ordered else 0.0
    return OCRResult(text=text, lines=ordered, mean_confidence=round(mean_conf, 4), engine=engine)


class PaddleOCRBackend:
    """Wraps ``paddleocr.PaddleOCR`` (3.x) as a lazily-initialised singleton.

    Configuration (environment variables):
    - ``OCR_LANG`` (default ``en``)
    - ``OCR_DEVICE`` (default ``cpu``)
    - ``OCR_VERSION`` (optional, e.g. ``PP-OCRv5``; default = paddleocr default)
    - ``OCR_ENABLE_MKLDNN`` (default ``false``; oneDNN is disabled because
      PaddlePaddle 3.3.x fails on the PP-OCRv6 models with it enabled)
    - ``OCR_USE_TEXTLINE_ORIENTATION`` (default ``false``)
    """

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    @property
    def engine_name(self) -> str:
        version = os.getenv("OCR_VERSION")
        return f"paddleocr:{version}" if version else "paddleocr"

    def _load(self):
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is not None:
                return self._engine
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise OCRUnavailableError(
                    "PaddleOCR is not installed. Install `paddlepaddle` and "
                    "`paddleocr` (see backend/requirements.txt)."
                ) from exc

            kwargs = dict(
                lang=os.getenv("OCR_LANG", "en"),
                device=os.getenv("OCR_DEVICE", "cpu"),
                enable_mkldnn=_env_bool("OCR_ENABLE_MKLDNN", False),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=_env_bool("OCR_USE_TEXTLINE_ORIENTATION", False),
            )
            version = os.getenv("OCR_VERSION")
            if version:
                kwargs["ocr_version"] = version
            try:
                self._engine = PaddleOCR(**kwargs)
            except Exception as exc:  # model download / paddle init failures
                raise OCRUnavailableError(f"Failed to initialise PaddleOCR: {exc}") from exc
            return self._engine

    def extract(self, image_bytes: bytes) -> OCRResult:
        image = decode_image(image_bytes)
        engine = self._load()
        results = engine.predict(image)

        lines: List[OCRLine] = []
        for page in results:
            texts = page.get("rec_texts", []) or []
            scores = page.get("rec_scores", []) or []
            polys = page.get("rec_polys", []) or []
            for idx, text in enumerate(texts):
                text = str(text).strip()
                if not text:
                    continue
                score = float(scores[idx]) if idx < len(scores) else 0.0
                bbox = _bbox_from_poly(polys[idx]) if idx < len(polys) else [0, 0, 0, 0]
                lines.append(OCRLine(text=text, confidence=round(score, 4), bbox=bbox))
        return build_result(lines, self.engine_name)


_default_backend: OCRBackend = PaddleOCRBackend()


def get_ocr_backend() -> OCRBackend:
    return _default_backend


def set_ocr_backend(backend: OCRBackend) -> None:
    """Override the OCR backend (used by tests to avoid loading Paddle)."""
    global _default_backend
    _default_backend = backend


def extract_text(image_bytes: bytes) -> OCRResult:
    return get_ocr_backend().extract(image_bytes)
