"""Unit tests for burst grouping and selection."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from photos_pipeline.modules.culling import BurstGroup, BurstGrouper, BurstSelector
from photos_pipeline.modules.ingestion import ImageRecord


def make_record(
    path: Path,
    *,
    camera_make: str = "Canon",
    camera_model: str = "R5",
    capture_datetime: datetime | None = None,
    blur_score: float | None = None,
    aesthetic_score: float | None = None,
    cull_reason: str | None = None,
) -> ImageRecord:
    """Build a minimal ImageRecord for burst tests."""
    record = ImageRecord(
        path=path,
        format="jpeg",
        camera_make=camera_make,
        camera_model=camera_model,
        capture_datetime=capture_datetime,
    )
    record.blur_score = blur_score
    record.aesthetic_score = aesthetic_score
    record.cull_reason = cull_reason
    return record


@pytest.mark.unit
def test_group_uses_capture_time_and_keeps_cameras_separate() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(Path("canon-1.jpg"), capture_datetime=t0),
        make_record(
            Path("sony-1.jpg"),
            camera_make="Sony",
            camera_model="A7IV",
            capture_datetime=t0 + timedelta(seconds=0.5),
        ),
        make_record(Path("canon-2.jpg"), capture_datetime=t0 + timedelta(seconds=1)),
        make_record(Path("canon-3.jpg"), capture_datetime=t0 + timedelta(seconds=5)),
        make_record(Path("canon-4.jpg"), capture_datetime=t0 + timedelta(seconds=6)),
    ]

    groups = BurstGrouper(burst_gap_seconds=2.0).group(records)

    assert len(groups) == 2
    assert [record.path.name for record in groups[0].images] == ["canon-1.jpg", "canon-2.jpg"]
    assert [record.path.name for record in groups[1].images] == ["canon-3.jpg", "canon-4.jpg"]
    assert all(record.camera_make == "Canon" for group in groups for record in group.images)


@pytest.mark.unit
def test_group_uses_mtime_fallback_when_capture_datetime_missing(tmp_path: Path) -> None:
    base_timestamp = 1_700_000_000.0

    first_path = tmp_path / "first.jpg"
    second_path = tmp_path / "second.jpg"
    late_path = tmp_path / "late.jpg"

    for path in (first_path, second_path, late_path):
        path.write_bytes(b"")

    os.utime(first_path, (base_timestamp, base_timestamp))
    os.utime(second_path, (base_timestamp + 1.0, base_timestamp + 1.0))
    os.utime(late_path, (base_timestamp + 10.0, base_timestamp + 10.0))

    records = [
        make_record(first_path),
        make_record(second_path),
        make_record(late_path),
    ]

    groups = BurstGrouper(burst_gap_seconds=2.0).group(records)

    assert len(groups) == 1
    assert [record.path.name for record in groups[0].images] == ["first.jpg", "second.jpg"]
    assert groups[0].group_id


@pytest.mark.unit
def test_group_ignores_single_images_outside_bursts() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(Path("burst-1.jpg"), capture_datetime=t0),
        make_record(Path("burst-2.jpg"), capture_datetime=t0 + timedelta(seconds=1)),
        make_record(Path("single.jpg"), capture_datetime=t0 + timedelta(seconds=10)),
    ]

    groups = BurstGrouper(burst_gap_seconds=2.0).group(records)

    assert len(groups) == 1
    assert [record.path.name for record in groups[0].images] == ["burst-1.jpg", "burst-2.jpg"]


@pytest.mark.unit
def test_select_best_picks_clearly_sharp_frame_from_five_image_sequence() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(
            Path("frame-1.jpg"),
            capture_datetime=t0,
            blur_score=10.0,
            aesthetic_score=0.2,
        ),
        make_record(
            Path("frame-2.jpg"),
            capture_datetime=t0 + timedelta(seconds=0.5),
            blur_score=12.0,
            aesthetic_score=0.3,
        ),
        make_record(
            Path("frame-3.jpg"),
            capture_datetime=t0 + timedelta(seconds=1),
            blur_score=250.0,
            aesthetic_score=0.9,
        ),
        make_record(
            Path("frame-4.jpg"),
            capture_datetime=t0 + timedelta(seconds=1.5),
            blur_score=15.0,
            aesthetic_score=0.4,
        ),
        make_record(
            Path("frame-5.jpg"),
            capture_datetime=t0 + timedelta(seconds=2),
            blur_score=8.0,
            aesthetic_score=0.1,
        ),
    ]
    group = BurstGrouper(burst_gap_seconds=2.0).group(records)[0]

    best = BurstSelector(blur_weight=0.6, aesthetic_weight=0.4).select_best(group)

    assert best.path.name == "frame-3.jpg"
    assert group.best is best


@pytest.mark.unit
def test_select_best_uses_composite_score() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(
            Path("first.jpg"),
            capture_datetime=t0,
            blur_score=300.0,
            aesthetic_score=0.1,
        ),
        make_record(
            Path("best.jpg"),
            capture_datetime=t0 + timedelta(seconds=1),
            blur_score=250.0,
            aesthetic_score=0.9,
            cull_reason="burst_duplicate",
        ),
        make_record(
            Path("third.jpg"),
            capture_datetime=t0 + timedelta(seconds=2),
            blur_score=100.0,
            aesthetic_score=0.2,
        ),
    ]
    group = BurstGroup(group_id="burst-1", images=records)

    best = BurstSelector().select_best(group)

    assert best is records[1]
    assert group.best is records[1]


@pytest.mark.unit
def test_select_best_tags_non_selected_frames_as_burst_duplicates() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    records = [
        make_record(
            Path("first.jpg"),
            capture_datetime=t0,
            blur_score=300.0,
            aesthetic_score=0.1,
        ),
        make_record(
            Path("best.jpg"),
            capture_datetime=t0 + timedelta(seconds=1),
            blur_score=250.0,
            aesthetic_score=0.9,
            cull_reason="burst_duplicate",
        ),
        make_record(
            Path("third.jpg"),
            capture_datetime=t0 + timedelta(seconds=2),
            blur_score=100.0,
            aesthetic_score=0.2,
        ),
    ]
    group = BurstGroup(group_id="burst-1", images=records)

    best = BurstSelector().select_best(group)

    assert best is records[1]
    assert best.burst_group_id == "burst-1"
    assert best.cull_reason is None
    assert records[0].burst_group_id == "burst-1"
    assert records[2].burst_group_id == "burst-1"
    assert records[0].cull_reason == "burst_duplicate"
    assert records[2].cull_reason == "burst_duplicate"


@pytest.mark.unit
def test_select_best_falls_back_to_blur_when_aesthetic_scores_missing() -> None:
    group = BurstGroup(
        group_id="burst-2",
        images=[
            make_record(Path("soft.jpg"), blur_score=25.0),
            make_record(Path("sharp.jpg"), blur_score=125.0),
        ],
    )

    best = BurstSelector().select_best(group)

    assert best.path.name == "sharp.jpg"
    assert group.images[0].cull_reason == "burst_duplicate"
    assert group.images[1].cull_reason is None


@pytest.mark.unit
def test_select_best_breaks_ties_by_latest_timestamp_then_path() -> None:
    t0 = datetime(2024, 1, 1, 12, 0, 0)
    earlier = make_record(Path("earlier.jpg"), capture_datetime=t0, blur_score=100.0)
    later = make_record(
        Path("later.jpg"),
        capture_datetime=t0 + timedelta(seconds=1),
        blur_score=100.0,
    )
    group = BurstGroup(group_id="burst-3", images=[earlier, later])

    best = BurstSelector().select_best(group)

    assert best is later

    alpha = make_record(Path("alpha.jpg"), capture_datetime=t0, blur_score=100.0)
    beta = make_record(Path("beta.jpg"), capture_datetime=t0, blur_score=100.0)
    same_time_group = BurstGroup(group_id="burst-4", images=[alpha, beta])

    same_time_best = BurstSelector().select_best(same_time_group)

    assert same_time_best is beta
