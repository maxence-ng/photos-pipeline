"""Unit tests for BlurDetector."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from photos_pipeline.modules.culling import BlurDetector
from photos_pipeline.modules.ingestion import ImageRecord

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sharp_image() -> np.ndarray:
    """200×200 checkerboard — high-frequency pattern → high Laplacian variance."""
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    for i in range(0, 200, 20):
        for j in range(0, 200, 20):
            if (i // 20 + j // 20) % 2 == 0:
                img[i : i + 20, j : j + 20] = 255
    return img


@pytest.fixture
def blurry_image(sharp_image: np.ndarray) -> np.ndarray:
    """Heavily blurred version of the checkerboard."""
    return cv2.GaussianBlur(sharp_image, (51, 51), 0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_score_sharp(sharp_image: np.ndarray) -> None:
    assert BlurDetector().score(sharp_image) > 200


@pytest.mark.unit
def test_score_blurry(blurry_image: np.ndarray) -> None:
    assert BlurDetector().score(blurry_image) < 50


@pytest.mark.unit
def test_is_blurry_false_for_sharp(sharp_image: np.ndarray) -> None:
    assert BlurDetector().is_blurry(sharp_image) is False


@pytest.mark.unit
def test_is_blurry_true_for_blurry(blurry_image: np.ndarray) -> None:
    assert BlurDetector().is_blurry(blurry_image) is True


@pytest.mark.unit
def test_custom_threshold(sharp_image: np.ndarray) -> None:
    assert BlurDetector().is_blurry(sharp_image, threshold=1e9) is True


@pytest.mark.unit
def test_imagerecord_blur_fields() -> None:
    record = ImageRecord(path=Path("photo.jpg"), format="jpeg")
    record.blur_score = 42.5
    record.cull_reason = "too blurry"
    assert record.blur_score == 42.5
    assert record.cull_reason == "too blurry"


@pytest.mark.unit
def test_process_sets_blur_score_on_sharp(sharp_image: np.ndarray) -> None:
    record = ImageRecord(path=Path("photo.jpg"), format="jpeg", thumbnail=sharp_image)
    BlurDetector().process(record)
    assert record.blur_score is not None
    assert record.blur_score > 200
    assert record.cull_reason is None  # sharp — not culled


@pytest.mark.unit
def test_process_sets_cull_reason_on_blurry(blurry_image: np.ndarray) -> None:
    record = ImageRecord(path=Path("photo.jpg"), format="jpeg", thumbnail=blurry_image)
    BlurDetector().process(record)
    assert record.blur_score is not None
    assert record.blur_score < 50
    assert record.cull_reason == "blur"


@pytest.mark.unit
def test_process_raises_without_thumbnail() -> None:
    record = ImageRecord(path=Path("photo.jpg"), format="jpeg")
    with pytest.raises(ValueError, match="No thumbnail"):
        BlurDetector().process(record)


@pytest.mark.unit
def test_config_default_threshold() -> None:
    """BlurDetector picks up blur_threshold from config (env-var wiring)."""
    import os
    from photos_pipeline.config import get_settings

    # Patch via env var; clear lru_cache so the new value is read
    original = os.environ.get("PHOTOS_PIPELINE_BLUR_THRESHOLD")
    os.environ["PHOTOS_PIPELINE_BLUR_THRESHOLD"] = "42.0"
    get_settings.cache_clear()
    try:
        assert BlurDetector().threshold == 42.0
    finally:
        if original is None:
            del os.environ["PHOTOS_PIPELINE_BLUR_THRESHOLD"]
        else:
            os.environ["PHOTOS_PIPELINE_BLUR_THRESHOLD"] = original
        get_settings.cache_clear()


@pytest.mark.unit
def test_process_clears_stale_blur_reason(sharp_image: np.ndarray) -> None:
    """process() clears cull_reason='blur' when image is no longer blurry."""
    record = ImageRecord(path=Path("photo.jpg"), format="jpeg", thumbnail=sharp_image)
    record.cull_reason = "blur"  # simulate a previous pass
    BlurDetector().process(record)
    assert record.cull_reason is None
