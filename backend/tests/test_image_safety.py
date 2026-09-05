"""Tests for image validation, dimension safety, and decompression bomb protection."""

import io
import pytest
from PIL import Image

from backend.app.services.ocr_service import (
    InvalidImageError,
    MAX_IMAGE_DIMENSION,
    decode_image,
)


def _png_with_size(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_valid_image_decodes_successfully():
    data = _png_with_size(100, 100)
    arr = decode_image(data)
    assert arr.shape == (100, 100, 3)


def test_empty_bytes_raises_invalid_image_error():
    with pytest.raises(InvalidImageError, match="empty"):
        decode_image(b"")


def test_corrupt_bytes_raises_invalid_image_error():
    with pytest.raises(InvalidImageError, match="not a valid image"):
        decode_image(b"GIF89a corrupted random binary string")


def test_oversized_dimension_rejected():
    """Images exceeding MAX_IMAGE_DIMENSION are rejected before memory allocation."""
    # We create a small header stating large dimensions or test boundary check
    with pytest.raises(InvalidImageError, match="exceeds maximum limit"):
        decode_image(_png_with_size(MAX_IMAGE_DIMENSION + 10, 10))
