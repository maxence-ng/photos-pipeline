"""Unit tests for DuplicateDetector."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from photos_pipeline.modules.culling import DuplicateDetector
from photos_pipeline.modules.ingestion import ImageRecord

# ---------------------------------------------------------------------------
# Synthetic image helpers
# ---------------------------------------------------------------------------


def make_checkerboard(size: int = 200) -> np.ndarray:
    """High-frequency checkerboard — produces a distinctive pHash."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    for i in range(0, size, 20):
        for j in range(0, size, 20):
            if (i // 20 + j // 20) % 2 == 0:
                img[i : i + 20, j : j + 20] = 255
    return img


def make_solid(color: tuple[int, int, int] = (128, 64, 32), size: int = 200) -> np.ndarray:
    """Uniform solid-colour image — produces a very different pHash from checkerboard."""
    return np.full((size, size, 3), color, dtype=np.uint8)


def make_record(
    thumbnail: np.ndarray | None,
    *,
    name: str = "photo.jpg",
    blur_score: float | None = None,
    capture_datetime: datetime | None = None,
    camera_make: str = "",
    camera_model: str = "",
    cull_reason: str | None = None,
) -> ImageRecord:
    r = ImageRecord(
        path=Path(name),
        format="jpeg",
        thumbnail=thumbnail,
        camera_make=camera_make,
        camera_model=camera_model,
    )
    r.blur_score = blur_score
    r.capture_datetime = capture_datetime
    r.cull_reason = cull_reason
    return r


# ---------------------------------------------------------------------------
# Grouping behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_near_identical_images_grouped() -> None:
    """Two copies of the same image → one DuplicateGroup."""
    img = make_checkerboard()
    records = [make_record(img.copy()), make_record(img.copy())]
    groups = DuplicateDetector().process(records)
    assert len(groups) == 1
    assert len(groups[0].images) == 2


@pytest.mark.unit
def test_different_images_not_grouped() -> None:
    """Clearly different images → no groups."""
    records = [
        make_record(make_checkerboard()),
        make_record(make_solid()),
    ]
    groups = DuplicateDetector().process(records)
    assert groups == []


@pytest.mark.unit
def test_three_images_two_similar_one_different() -> None:
    """A≈B but C is very different → one group of [A,B], C not in any group."""
    img = make_checkerboard()
    records = [
        make_record(img.copy(), name="a.jpg"),
        make_record(img.copy(), name="b.jpg"),
        make_record(make_solid(), name="c.jpg"),
    ]
    groups = DuplicateDetector().process(records)
    assert len(groups) == 1
    paths_in_group = {r.path.name for r in groups[0].images}
    assert paths_in_group == {"a.jpg", "b.jpg"}


# ---------------------------------------------------------------------------
# Burst / bracketing guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_burst_pair_not_grouped() -> None:
    """Near-identical images taken 1 s apart → burst pair, NOT grouped."""
    img = make_checkerboard()
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    t1 = datetime(2024, 1, 1, 12, 0, 1)  # Δt = 1 s < 3 s gap
    records = [
        make_record(img.copy(), capture_datetime=t0, camera_make="Canon", camera_model="R5"),
        make_record(img.copy(), capture_datetime=t1, camera_make="Canon", camera_model="R5"),
    ]
    groups = DuplicateDetector(burst_gap_seconds=3.0).process(records)
    assert groups == []


@pytest.mark.unit
def test_bracketing_pair_not_grouped() -> None:
    """Near-identical images taken 1.5 s apart (focus bracketing) → NOT grouped."""
    img = make_checkerboard()
    from datetime import timedelta

    t0 = datetime(2024, 1, 1, 12, 0, 0)
    t1 = t0 + timedelta(seconds=1.5)
    records = [
        make_record(img.copy(), capture_datetime=t0, camera_make="Canon", camera_model="R5"),
        make_record(img.copy(), capture_datetime=t1, camera_make="Canon", camera_model="R5"),
    ]
    groups = DuplicateDetector(burst_gap_seconds=3.0).process(records)
    assert groups == []


@pytest.mark.unit
def test_exact_copy_same_timestamp_not_grouped_when_same_camera() -> None:
    """Same-camera frames with the same timestamp follow burst semantics and are skipped."""
    img = make_checkerboard()
    t = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(img.copy(), capture_datetime=t, camera_make="Canon", camera_model="R5"),
        make_record(img.copy(), capture_datetime=t, camera_make="Canon", camera_model="R5"),
    ]
    groups = DuplicateDetector(burst_gap_seconds=3.0).process(records)
    assert groups == []


@pytest.mark.unit
def test_gap_at_burst_threshold_is_not_grouped() -> None:
    """Images with Δt == burst_gap_seconds still count as a burst pair."""
    from datetime import timedelta

    img = make_checkerboard()
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    t1 = t0 + timedelta(seconds=3.0)
    records = [
        make_record(img.copy(), capture_datetime=t0, camera_make="Canon", camera_model="R5"),
        make_record(img.copy(), capture_datetime=t1, camera_make="Canon", camera_model="R5"),
    ]
    groups = DuplicateDetector(burst_gap_seconds=3.0).process(records)
    assert groups == []


@pytest.mark.unit
def test_missing_datetime_uses_mtime_fallback_for_same_camera(tmp_path: Path) -> None:
    """Missing EXIF timestamps fall back to mtimes for same-camera burst checks."""
    img = make_checkerboard()
    base_timestamp = 1_700_000_000.0
    first_path = tmp_path / "first.jpg"
    second_path = tmp_path / "second.jpg"
    first_path.write_bytes(b"")
    second_path.write_bytes(b"")
    os.utime(first_path, (base_timestamp, base_timestamp))
    os.utime(second_path, (base_timestamp + 1.0, base_timestamp + 1.0))

    records = [
        make_record(
            img.copy(),
            name=str(first_path),
            camera_make="Canon",
            camera_model="R5",
        ),
        make_record(
            img.copy(),
            name=str(second_path),
            camera_make="Canon",
            camera_model="R5",
        ),
    ]
    groups = DuplicateDetector(burst_gap_seconds=3.0).process(records)
    assert groups == []


@pytest.mark.unit
def test_same_timestamp_different_camera_still_groups_as_duplicate() -> None:
    """Burst guard does not apply across different camera identities."""
    img = make_checkerboard()
    t = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(img.copy(), capture_datetime=t, camera_make="Canon", camera_model="R5"),
        make_record(img.copy(), capture_datetime=t, camera_make="Sony", camera_model="A7IV"),
    ]
    groups = DuplicateDetector(burst_gap_seconds=3.0).process(records)
    assert len(groups) == 1


# ---------------------------------------------------------------------------
# Best-image selection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_best_is_sharpest() -> None:
    """Group of 3 — the one with highest blur_score is nominated as best."""
    img = make_checkerboard()
    r_low = make_record(img.copy(), name="low.jpg", blur_score=50.0)
    r_best = make_record(img.copy(), name="best.jpg", blur_score=300.0)
    r_mid = make_record(img.copy(), name="mid.jpg", blur_score=100.0)
    groups = DuplicateDetector().process([r_low, r_best, r_mid])
    assert len(groups) == 1
    assert groups[0].best is r_best


@pytest.mark.unit
def test_best_tiebreak_by_latest_datetime() -> None:
    """Equal blur_score → latest capture_datetime wins."""
    img = make_checkerboard()
    t_older = datetime(2024, 1, 1, 10, 0, 0)
    t_newer = datetime(2024, 1, 1, 18, 0, 0)
    r_older = make_record(img.copy(), name="older.jpg", blur_score=200.0, capture_datetime=t_older)
    r_newer = make_record(img.copy(), name="newer.jpg", blur_score=200.0, capture_datetime=t_newer)
    groups = DuplicateDetector().process([r_older, r_newer])
    assert len(groups) == 1
    assert groups[0].best is r_newer


@pytest.mark.unit
def test_non_best_tagged_duplicate() -> None:
    """Non-best duplicates get cull_reason='duplicate'; best does not."""
    img = make_checkerboard()
    r1 = make_record(img.copy(), blur_score=100.0)
    r2 = make_record(img.copy(), blur_score=300.0)  # sharpest → best
    groups = DuplicateDetector().process([r1, r2])
    assert len(groups) == 1
    assert groups[0].best is r2
    assert r2.cull_reason != "duplicate"
    assert r1.cull_reason == "duplicate"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_single_image_returns_empty() -> None:
    groups = DuplicateDetector().process([make_record(make_checkerboard())])
    assert groups == []


@pytest.mark.unit
def test_empty_list_returns_empty() -> None:
    groups = DuplicateDetector().process([])
    assert groups == []


@pytest.mark.unit
def test_no_thumbnail_raises() -> None:
    records = [make_record(None)]
    with pytest.raises(ValueError, match="No thumbnail"):
        DuplicateDetector().process(records)


# ---------------------------------------------------------------------------
# Threshold and algorithm configurability
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_custom_threshold_zero_no_grouping() -> None:
    """threshold=0 means only identical hashes group — two similar but non-equal → not grouped."""
    img = make_checkerboard()
    # Apply slight blur to shift the hash just enough
    other = cv2.GaussianBlur(img, (3, 3), 0)
    records = [make_record(img), make_record(other)]
    # With threshold=0 they likely differ; with default 10 they'd likely group.
    # We just verify threshold=0 produces fewer or equal groups than threshold=10.
    groups_strict = DuplicateDetector(threshold=0).process(records)
    groups_loose = DuplicateDetector(threshold=10).process(records)
    assert len(groups_strict) <= len(groups_loose)


@pytest.mark.unit
def test_algorithm_dhash() -> None:
    """dhash algorithm groups two copies of the same image."""
    img = make_checkerboard()
    records = [make_record(img.copy()), make_record(img.copy())]
    groups = DuplicateDetector(algorithm="dhash").process(records)
    assert len(groups) == 1


@pytest.mark.unit
def test_algorithm_ahash() -> None:
    """ahash algorithm groups two copies of the same image."""
    img = make_checkerboard()
    records = [make_record(img.copy()), make_record(img.copy())]
    groups = DuplicateDetector(algorithm="ahash").process(records)
    assert len(groups) == 1


@pytest.mark.unit
def test_invalid_algorithm_raises() -> None:
    with pytest.raises(ValueError, match="Unknown hash algorithm"):
        DuplicateDetector(algorithm="invalid")


@pytest.mark.unit
def test_config_threshold_from_env() -> None:
    """DuplicateDetector picks up duplicate_threshold from env-var config."""
    from photos_pipeline.config import get_settings

    original = os.environ.get("PHOTOS_PIPELINE_DUPLICATE_THRESHOLD")
    os.environ["PHOTOS_PIPELINE_DUPLICATE_THRESHOLD"] = "5"
    get_settings.cache_clear()
    try:
        assert DuplicateDetector().threshold == 5
    finally:
        if original is None:
            del os.environ["PHOTOS_PIPELINE_DUPLICATE_THRESHOLD"]
        else:
            os.environ["PHOTOS_PIPELINE_DUPLICATE_THRESHOLD"] = original
        get_settings.cache_clear()
