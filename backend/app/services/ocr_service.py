"""OCR service built on PaddleOCR 3.x (``PaddleOCR.predict`` pipeline API).

The PaddleOCR engine is loaded lazily on first use so the API can boot on
machines that do not have PaddlePaddle installed; such machines get a clear
``OCRUnavailableError`` from the OCR endpoints instead of an import crash.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Sequence

import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError


logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


MAX_IMAGE_DIMENSION = 8000
MAX_IMAGE_PIXELS = 25_000_000

# Set Pillow decompression bomb threshold
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class OCRUnavailableError(RuntimeError):
    """Raised when the OCR engine cannot be loaded (e.g. paddle not installed)."""


class InvalidImageError(ValueError):
    """Raised when the uploaded bytes are not a decodable image or exceed safe dimensions."""


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
    # The exact array handed to the OCR engine (post decode + preprocess), so
    # callers (pipeline_service) can crop per-question regions for the visual
    # fallback (A5) without re-decoding the upload -- bbox coordinates from
    # `lines` are in this array's coordinate space, not the original upload's.
    # Never serialised into an API response; internal use only.
    image: Optional[np.ndarray] = None

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OCRBackend(Protocol):
    def extract(self, image_bytes: bytes) -> OCRResult: ...


def decode_image(image_bytes: bytes) -> np.ndarray:
    """Decode uploaded bytes into an RGB ``numpy`` array (H, W, 3) safely."""
    if not image_bytes:
        raise InvalidImageError("Uploaded image data is empty.")
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            if width <= 0 or height <= 0:
                raise InvalidImageError("Image has invalid zero dimensions.")
            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                raise InvalidImageError(
                    f"Image dimension ({width}x{height}) exceeds maximum limit ({MAX_IMAGE_DIMENSION}px)."
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise InvalidImageError(
                    f"Image total pixels ({width * height}) exceed maximum limit ({MAX_IMAGE_PIXELS})."
                )
            return np.asarray(img.convert("RGB"))
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("Uploaded file is not a valid image.") from exc



DEFAULT_TARGET_LONG_SIDE = 2000


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Light, configurable preprocessing applied only to the array handed to
    the OCR engine -- ``decode_image``'s own output (used directly by callers
    and by ``test_image_safety.py``) is never mutated by this function.

    Chosen deliberately narrow, not a full image-enhancement pipeline:

    - **Upscale small images** (``OCR_UPSCALE``, default on): a phone photo
      or a small scan can leave thin pen/pencil strokes only a few pixels
      wide, which the detector under-segments or drops entirely. Upscaling
      to a minimum long-side (``OCR_TARGET_LONG_SIDE``, default 2000px)
      while preserving aspect ratio gives the detector more pixels to work
      with. Never downscales.
    - **Autocontrast** (``OCR_AUTOCONTRAST``, default on): stretches the
      pixel value histogram (1% cutoff at each end) so faint pencil or a
      washed-out phone photo gets real black/white separation. Cheap and,
      unlike a fixed threshold, self-adjusting per image.
    - **Median denoise** (``OCR_DENOISE``, default OFF): can help with
      paper-texture/JPEG noise but a large window also erodes thin strokes,
      and this has not been validated against a real handwriting sample in
      this repository (none exists) -- left as an explicit opt-in rather
      than a default, so a user who enables it does so knowingly.

    Deliberately NOT done: deskewing. That needs robust angle estimation
    (typically OpenCV/Hough-transform territory) which is not a dependency
    of this project; a naive heuristic risks rotating legible text into
    illegible text, which would be "artificially modifying the answer" --
    exactly what this function must not do.
    """
    img = Image.fromarray(image)

    if _env_bool("OCR_AUTOCONTRAST", True):
        img = ImageOps.autocontrast(img, cutoff=1)

    if _env_bool("OCR_DENOISE", False):
        img = img.filter(ImageFilter.MedianFilter(size=3))

    if _env_bool("OCR_UPSCALE", True):
        target_long_side = int(os.getenv("OCR_TARGET_LONG_SIDE", str(DEFAULT_TARGET_LONG_SIDE)))
        long_side = max(img.width, img.height)
        if 0 < long_side < target_long_side:
            scale = target_long_side / long_side
            new_size = (round(img.width * scale), round(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

    return np.asarray(img)


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


def build_result(lines: List[OCRLine], engine: str, image: Optional[np.ndarray] = None) -> OCRResult:
    ordered = order_lines(lines)
    text = "\n".join(l.text for l in ordered)
    mean_conf = float(np.mean([l.confidence for l in ordered])) if ordered else 0.0
    return OCRResult(text=text, lines=ordered, mean_confidence=round(mean_conf, 4), engine=engine, image=image)


def crop_region(image: np.ndarray, bbox: Sequence[int], padding: int = 12) -> bytes:
    """Crop ``bbox`` out of ``image`` (with a small padding for context) and
    PNG-encode it. Used to send a specific answer region to Gemini's visual
    fallback (A5/A3) instead of the whole answer sheet. Coordinates are
    clamped to the image bounds; an empty/degenerate crop falls back to the
    full image rather than raising.
    """
    h, w = image.shape[:2]
    x0, y0, x1, y1 = bbox
    x0 = max(0, int(x0) - padding)
    y0 = max(0, int(y0) - padding)
    x1 = min(w, int(x1) + padding)
    y1 = min(h, int(y1) + padding)
    if x1 <= x0 or y1 <= y0:
        crop = image
    else:
        crop = image[y0:y1, x0:x1]
    buf = io.BytesIO()
    Image.fromarray(crop).save(buf, format="PNG")
    return buf.getvalue()


def union_bbox(boxes: Sequence[Sequence[int]]) -> Optional[List[int]]:
    """Smallest bbox enclosing all of ``boxes``, or None if empty."""
    if not boxes:
        return None
    xs0 = [b[0] for b in boxes]
    ys0 = [b[1] for b in boxes]
    xs1 = [b[2] for b in boxes]
    ys1 = [b[3] for b in boxes]
    return [min(xs0), min(ys0), max(xs1), max(ys1)]


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
                logger.exception("Failed to initialise PaddleOCR")
                raise OCRUnavailableError(
                    "OCR engine is unavailable. Check server logs."
                ) from exc
            return self._engine

    def extract(self, image_bytes: bytes) -> OCRResult:
        image = decode_image(image_bytes)
        image = preprocess_for_ocr(image)
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
        return build_result(lines, self.engine_name, image=image)


_default_backend: OCRBackend = PaddleOCRBackend()


def get_ocr_backend() -> OCRBackend:
    return _default_backend


def set_ocr_backend(backend: OCRBackend) -> None:
    """Override the OCR backend (used by tests to avoid loading Paddle)."""
    global _default_backend
    _default_backend = backend


# OCR is a deterministic, pure function of (image bytes, preprocessing config)
# -- safe to cache. The "Retry Evaluation" flow (frontend) re-sends the exact
# same image on every retry, which previously re-ran PaddleOCR from scratch
# each time; this makes a retry after a Gemini-only failure skip straight to
# evaluation. Bounded (OCR_CACHE_MAX_ENTRIES, default 32) with LRU eviction so
# a busy server can't grow this unboundedly. Keyed purely by image content
# hash -- there is no student/session identity in the key, so a cache hit can
# never mix one student's OCR result into another's evaluation; two different
# students submitting byte-identical images is not a leak, it's the same OCR
# result being (correctly) reused for the same input.
_ocr_cache: "OrderedDict[str, OCRResult]" = OrderedDict()
_ocr_cache_lock = threading.Lock()


def _ocr_cache_max_entries() -> int:
    try:
        return int(os.getenv("OCR_CACHE_MAX_ENTRIES", "32"))
    except ValueError:
        return 32


def _ocr_cache_enabled() -> bool:
    return _env_bool("OCR_CACHE_ENABLED", True)


def clear_ocr_cache() -> None:
    """Used by tests to guarantee isolation between cases."""
    with _ocr_cache_lock:
        _ocr_cache.clear()


def extract_text(image_bytes: bytes) -> OCRResult:
    if not _ocr_cache_enabled():
        return get_ocr_backend().extract(image_bytes)

    key = hashlib.sha256(image_bytes).hexdigest()
    with _ocr_cache_lock:
        cached = _ocr_cache.get(key)
        if cached is not None:
            _ocr_cache.move_to_end(key)
            logger.debug("OCR cache hit for %s", key[:12])
            return cached

    result = get_ocr_backend().extract(image_bytes)

    with _ocr_cache_lock:
        _ocr_cache[key] = result
        _ocr_cache.move_to_end(key)
        while len(_ocr_cache) > _ocr_cache_max_entries():
            _ocr_cache.popitem(last=False)

    return result
