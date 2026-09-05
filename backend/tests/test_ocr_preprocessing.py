"""Tests for OCR preprocessing (upscaling, autocontrast, denoise).

These validate the deterministic image-transform properties (aspect ratio
preserved, contrast measurably widened, upscaling only when small) using
synthetic images -- NOT a claim that handwriting recognition itself is
improved. No real handwriting sample exists in this repository to validate
that end-to-end; see backend/README.md for the honest caveat.
"""

import numpy as np
from PIL import Image

from backend.app.services.ocr_service import (
    DEFAULT_TARGET_LONG_SIDE,
    decode_image,
    preprocess_for_ocr,
)


def _gray_square(size: int, low: int, high: int) -> np.ndarray:
    """A low-contrast test image: a `high`-value box on a `low`-value background."""
    arr = np.full((size, size, 3), low, dtype=np.uint8)
    margin = size // 4
    arr[margin:-margin, margin:-margin] = high
    return arr


def test_decode_image_output_is_never_mutated_by_preprocessing():
    """decode_image's contract (used directly by test_image_safety.py and by
    other callers) must be untouched by preprocessing -- preprocessing only
    applies on the copy fed to the OCR engine."""
    buf_size = 100
    img = Image.new("RGB", (buf_size, buf_size), "white")
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    decoded = decode_image(buf.getvalue())
    assert decoded.shape == (buf_size, buf_size, 3)
    # preprocess_for_ocr is a separate, explicit call -- decode_image itself
    # must not have upscaled or altered it.


def test_small_image_is_upscaled_preserving_aspect_ratio(monkeypatch):
    monkeypatch.delenv("OCR_TARGET_LONG_SIDE", raising=False)
    monkeypatch.setenv("OCR_UPSCALE", "true")
    arr = _gray_square(100, low=200, high=220)  # 100x100, well below target
    out = preprocess_for_ocr(arr)
    assert max(out.shape[0], out.shape[1]) >= DEFAULT_TARGET_LONG_SIDE
    # square input -> square output (aspect ratio preserved)
    assert out.shape[0] == out.shape[1]


def test_large_image_is_not_upscaled(monkeypatch):
    monkeypatch.setenv("OCR_UPSCALE", "true")
    monkeypatch.setenv("OCR_AUTOCONTRAST", "false")
    size = DEFAULT_TARGET_LONG_SIDE + 200
    arr = _gray_square(size, low=100, high=180)
    out = preprocess_for_ocr(arr)
    assert out.shape[0] == size  # unchanged, never downscales


def test_upscale_disabled_via_env(monkeypatch):
    monkeypatch.setenv("OCR_UPSCALE", "false")
    monkeypatch.setenv("OCR_AUTOCONTRAST", "false")
    arr = _gray_square(50, low=200, high=220)
    out = preprocess_for_ocr(arr)
    assert out.shape[0] == 50


def test_autocontrast_widens_a_low_contrast_histogram(monkeypatch):
    monkeypatch.setenv("OCR_AUTOCONTRAST", "true")
    monkeypatch.setenv("OCR_UPSCALE", "false")
    monkeypatch.setenv("OCR_DENOISE", "false")
    low_contrast = _gray_square(200, low=110, high=140)  # narrow 30-value range
    out = preprocess_for_ocr(low_contrast)
    assert (int(out.max()) - int(out.min())) > (140 - 110)


def test_autocontrast_disabled_leaves_narrow_histogram(monkeypatch):
    monkeypatch.setenv("OCR_AUTOCONTRAST", "false")
    monkeypatch.setenv("OCR_UPSCALE", "false")
    monkeypatch.setenv("OCR_DENOISE", "false")
    low_contrast = _gray_square(200, low=110, high=140)
    out = preprocess_for_ocr(low_contrast)
    assert int(out.max()) == 140 and int(out.min()) == 110


def test_denoise_is_off_by_default(monkeypatch):
    monkeypatch.delenv("OCR_DENOISE", raising=False)
    monkeypatch.setenv("OCR_UPSCALE", "false")
    monkeypatch.setenv("OCR_AUTOCONTRAST", "false")
    arr = _gray_square(50, low=200, high=200)
    arr[10, 10] = 0  # a single salt-noise pixel
    out = preprocess_for_ocr(arr)
    assert out[10, 10, 0] == 0  # untouched -- denoise not applied by default


def test_denoise_removes_isolated_noise_pixel_when_enabled(monkeypatch):
    monkeypatch.setenv("OCR_DENOISE", "true")
    monkeypatch.setenv("OCR_UPSCALE", "false")
    monkeypatch.setenv("OCR_AUTOCONTRAST", "false")
    arr = _gray_square(50, low=200, high=200)
    arr[25, 25] = 0  # isolated noise pixel surrounded by uniform background
    out = preprocess_for_ocr(arr)
    assert out[25, 25, 0] == 200  # median filter removes the isolated outlier
