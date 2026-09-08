"""Tests for the OCR result cache (A9) -- deterministic, content-hash-keyed,
bounded, and never a cross-request/cross-student leak vector since the key
is the image bytes alone.
"""

import pytest

from backend.app.services import ocr_service
from backend.app.services.ocr_service import OCRResult


class _CountingBackend:
    """Returns a distinct result each call so a cache hit is unambiguous."""

    def __init__(self):
        self.calls = 0

    def extract(self, image_bytes: bytes) -> OCRResult:
        self.calls += 1
        return OCRResult(text=f"call-{self.calls}", mean_confidence=0.9, engine="fake")


@pytest.fixture(autouse=True)
def isolated_cache():
    original = ocr_service.get_ocr_backend()
    ocr_service.clear_ocr_cache()
    yield
    ocr_service.set_ocr_backend(original)
    ocr_service.clear_ocr_cache()


def test_identical_bytes_hit_the_cache_on_second_call(monkeypatch):
    monkeypatch.setenv("OCR_CACHE_ENABLED", "true")
    backend = _CountingBackend()
    ocr_service.set_ocr_backend(backend)

    first = ocr_service.extract_text(b"same-image-bytes")
    second = ocr_service.extract_text(b"same-image-bytes")

    assert backend.calls == 1  # second call was a cache hit, not a re-run
    assert first.text == second.text == "call-1"


def test_different_bytes_are_not_conflated():
    backend = _CountingBackend()
    ocr_service.set_ocr_backend(backend)

    first = ocr_service.extract_text(b"image-one")
    second = ocr_service.extract_text(b"image-two")

    assert backend.calls == 2
    assert first.text != second.text


def test_cache_disabled_via_env_always_recomputes(monkeypatch):
    monkeypatch.setenv("OCR_CACHE_ENABLED", "false")
    backend = _CountingBackend()
    ocr_service.set_ocr_backend(backend)

    ocr_service.extract_text(b"same-bytes")
    ocr_service.extract_text(b"same-bytes")

    assert backend.calls == 2


def test_cache_respects_max_entries_bound(monkeypatch):
    monkeypatch.setenv("OCR_CACHE_ENABLED", "true")
    monkeypatch.setenv("OCR_CACHE_MAX_ENTRIES", "2")
    backend = _CountingBackend()
    ocr_service.set_ocr_backend(backend)

    ocr_service.extract_text(b"image-a")
    ocr_service.extract_text(b"image-b")
    ocr_service.extract_text(b"image-c")  # evicts image-a (LRU)

    # image-a should have been evicted -- re-fetching it recomputes (call count increases)
    calls_before = backend.calls
    ocr_service.extract_text(b"image-a")
    assert backend.calls == calls_before + 1
