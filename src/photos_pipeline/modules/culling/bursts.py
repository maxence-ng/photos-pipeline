"""Burst grouping and best-frame selection."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from photos_pipeline.modules.ingestion import ImageRecord

__all__ = ["BurstGroup", "BurstGrouper", "BurstSelector", "is_burst_pair"]


def _camera_identity(record: ImageRecord) -> tuple[str, str]:
    """Return a normalised camera identity for grouping."""
    return (record.camera_make.strip().casefold(), record.camera_model.strip().casefold())


def _resolved_effective_timestamp(record: ImageRecord) -> datetime | None:
    """Return the capture time, falling back to the file modification time."""
    if record.capture_datetime is not None:
        return record.capture_datetime
    try:
        return datetime.fromtimestamp(record.path.stat().st_mtime)
    except OSError:
        return None


def _effective_timestamp(record: ImageRecord) -> datetime:
    """Return an effective timestamp suitable for ordering records."""
    return _resolved_effective_timestamp(record) or datetime.min


def is_burst_pair(
    first: ImageRecord,
    second: ImageRecord,
    *,
    burst_gap_seconds: float,
) -> bool:
    """Return True when two records match burst-grouping semantics.

    Callers supply the gap explicitly so duplicate detection can align the
    semantics while still using its own configuration boundary.
    """
    if _camera_identity(first) != _camera_identity(second):
        return False

    first_timestamp = _resolved_effective_timestamp(first)
    second_timestamp = _resolved_effective_timestamp(second)
    if first_timestamp is None or second_timestamp is None:
        return False

    return abs((first_timestamp - second_timestamp).total_seconds()) <= burst_gap_seconds


@dataclass
class BurstGroup:
    """A time-adjacent set of images captured by the same camera."""

    group_id: str
    images: list[ImageRecord]
    best: ImageRecord | None = None


class BurstGrouper:
    """Group burst sequences based on camera identity and capture proximity."""

    def __init__(self, burst_gap_seconds: float | None = None) -> None:
        if burst_gap_seconds is None:
            from photos_pipeline.config import get_settings

            burst_gap_seconds = get_settings().burst_gap_seconds
        self.burst_gap_seconds = burst_gap_seconds

    def group(self, records: list[ImageRecord]) -> list[BurstGroup]:
        """Return burst groups with two or more records."""
        if len(records) < 2:
            return []

        records_by_camera: dict[tuple[str, str], list[ImageRecord]] = defaultdict(list)
        for record in records:
            records_by_camera[_camera_identity(record)].append(record)

        groups: list[BurstGroup] = []
        for camera_records in records_by_camera.values():
            ordered_records = sorted(
                camera_records,
                key=lambda record: (_effective_timestamp(record), str(record.path)),
            )

            current_group: list[ImageRecord] = []

            for record in ordered_records:
                if (
                    current_group
                    and is_burst_pair(
                        current_group[-1],
                        record,
                        burst_gap_seconds=self.burst_gap_seconds,
                    )
                ):
                    current_group.append(record)
                else:
                    if len(current_group) >= 2:
                        groups.append(
                            BurstGroup(group_id=str(uuid4()), images=current_group.copy())
                        )
                    current_group = [record]

            if len(current_group) >= 2:
                groups.append(BurstGroup(group_id=str(uuid4()), images=current_group.copy()))

        return sorted(
            groups,
            key=lambda group: (_effective_timestamp(group.images[0]), str(group.images[0].path)),
        )


class BurstSelector:
    """Select the best frame from a burst group."""

    def __init__(
        self,
        blur_weight: float | None = None,
        aesthetic_weight: float | None = None,
    ) -> None:
        if blur_weight is None or aesthetic_weight is None:
            from photos_pipeline.config import get_settings

            settings = get_settings()
            if blur_weight is None:
                blur_weight = settings.burst_blur_weight
            if aesthetic_weight is None:
                aesthetic_weight = settings.burst_aesthetic_weight

        self.blur_weight = blur_weight
        self.aesthetic_weight = aesthetic_weight

    @staticmethod
    def _normalise(values: list[float | None]) -> list[float]:
        """Normalise nullable scores to the 0..1 range."""
        resolved = [0.0 if value is None else float(value) for value in values]
        minimum = min(resolved)
        maximum = max(resolved)

        if maximum == minimum:
            return [1.0 for _ in resolved]

        scale = maximum - minimum
        return [(value - minimum) / scale for value in resolved]

    def select_best(self, group: BurstGroup) -> ImageRecord:
        """Select, store, and tag the best record in *group*."""
        if not group.images:
            raise ValueError("BurstGroup must contain at least one image")

        blur_scores = self._normalise([record.blur_score for record in group.images])
        use_aesthetic_scores = all(
            record.aesthetic_score is not None for record in group.images
        )
        aesthetic_scores = (
            self._normalise([record.aesthetic_score for record in group.images])
            if use_aesthetic_scores
            else [0.0 for _ in group.images]
        )

        def sort_key(
            candidate: tuple[ImageRecord, float, float],
        ) -> tuple[float, float, float, datetime, str]:
            record, blur_score, aesthetic_score = candidate
            composite_score = (
                self.blur_weight * blur_score + self.aesthetic_weight * aesthetic_score
                if use_aesthetic_scores
                else blur_score
            )
            return (
                composite_score,
                blur_score,
                aesthetic_score,
                _effective_timestamp(record),
                str(record.path),
            )

        best, _, _ = max(
            zip(group.images, blur_scores, aesthetic_scores, strict=True),
            key=sort_key,
        )
        group.best = best

        for record in group.images:
            record.burst_group_id = group.group_id
            if record is best:
                if record.cull_reason == "burst_duplicate":
                    record.cull_reason = None
                continue
            record.cull_reason = "burst_duplicate"

        return best
