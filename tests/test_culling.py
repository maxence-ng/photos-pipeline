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
