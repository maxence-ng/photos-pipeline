"""Duplicate detection using perceptual hashing (pHash/dHash/aHash)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import imagehash
import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from photos_pipeline.modules.ingestion import ImageRecord

__all__ = ["DuplicateDetector", "DuplicateGroup"]


@dataclass
class DuplicateGroup:
    """A cluster of near-identical images with a nominated best image."""

    images: list[ImageRecord]
    best: ImageRecord


class DuplicateDetector:
    """Detect near-duplicate images using perceptual hashing."""

    ALGORITHMS = {
        "phash": imagehash.phash,
        "dhash": imagehash.dhash,
        "ahash": imagehash.average_hash,
    }

    def __init__(
        self,
        threshold: int | None = None,
        algorithm: str | None = None,
        burst_gap_seconds: float | None = None,
    ) -> None:
        from photos_pipeline.config import get_settings

        settings = get_settings()
        self.threshold = threshold if threshold is not None else settings.duplicate_threshold
        self.algorithm = algorithm if algorithm is not None else settings.duplicate_hash_algorithm
        self.burst_gap_seconds = (
            burst_gap_seconds
            if burst_gap_seconds is not None
            else settings.duplicate_burst_gap_seconds
        )
        if self.algorithm not in self.ALGORITHMS:
            raise ValueError(
                f"Unknown hash algorithm {self.algorithm!r}. "
                f"Choose one of: {list(self.ALGORITHMS)}"
            )

    def compute_hash(self, thumbnail: np.ndarray) -> imagehash.ImageHash:
        """Compute a perceptual hash for a BGR thumbnail array."""
        pil = Image.fromarray(cv2.cvtColor(thumbnail, cv2.COLOR_BGR2RGB))
        return self.ALGORITHMS[self.algorithm](pil)

    def _is_burst_pair(self, a: ImageRecord, b: ImageRecord) -> bool:
        """Return True if a and b are part of a burst/bracketing sequence.

        Two images are burst if BOTH have capture_datetime, they differ by more
        than 0 seconds but less than burst_gap_seconds.
        """
        if a.capture_datetime is None or b.capture_datetime is None:
            return False
        delta = abs((a.capture_datetime - b.capture_datetime).total_seconds())
        return 0 < delta < self.burst_gap_seconds

    def _pick_best(self, group: list[ImageRecord]) -> ImageRecord:
        """Select the best image from a group: highest blur_score, then latest capture_datetime, then first."""

        def sort_key(r: ImageRecord):
            score = r.blur_score if r.blur_score is not None else -1.0
            dt = r.capture_datetime.timestamp() if r.capture_datetime is not None else 0.0
            return (score, dt)

        return max(group, key=sort_key)

    def process(self, records: list[ImageRecord]) -> list[DuplicateGroup]:
        """Group near-duplicate images and tag non-best duplicates.

        Args:
            records: ImageRecord objects, each must have a thumbnail.

        Returns:
            List of DuplicateGroup objects (only groups with ≥2 members).
            Non-best images within each group have cull_reason set to "duplicate".

        Raises:
            ValueError: If any record has no thumbnail.
        """
        if not records:
            return []

        # Compute hashes for all records
        hashes: list[imagehash.ImageHash] = []
        for record in records:
            if record.thumbnail is None:
                raise ValueError(f"No thumbnail available for {record.path}")
            hashes.append(self.compute_hash(record.thumbnail))

        n = len(records)

        # Build adjacency list: i -> set of j's that are near-duplicates of i
        adjacency: list[set[int]] = [set() for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                # Skip burst/bracketing pairs
                if self._is_burst_pair(records[i], records[j]):
                    continue
                distance = hashes[i] - hashes[j]
                if distance <= self.threshold:
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        # Find connected components via DFS
        visited: set[int] = set()
        groups: list[DuplicateGroup] = []

        for start in range(n):
            if start in visited:
                continue
            if not adjacency[start]:
                visited.add(start)
                continue
            # DFS
            component: list[int] = []
            stack = [start]
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                stack.extend(adjacency[node] - visited)

            if len(component) >= 2:
                group_records = [records[i] for i in component]
                best = self._pick_best(group_records)
                for r in group_records:
                    if r is not best:
                        r.cull_reason = "duplicate"
                groups.append(DuplicateGroup(images=group_records, best=best))

        return groups
