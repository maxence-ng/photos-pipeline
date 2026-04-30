"""Blur detection using Laplacian variance."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from photos_pipeline.modules.ingestion import ImageRecord

__all__ = ["BlurDetector"]


class BlurDetector:
    """Detect blur via Laplacian variance on a greyscale centre crop."""

    def __init__(self, threshold: float | None = None) -> None:
        if threshold is None:
            from photos_pipeline.config import get_settings
            threshold = get_settings().blur_threshold
        self.threshold = threshold

    def score(self, image: np.ndarray) -> float:
        """Return the Laplacian variance of the centre 80%-area crop of *image*."""
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = grey.shape
        # Keep sqrt(0.8) of each dimension → 80% of total area
        factor = math.sqrt(0.8)
        h_keep = int(h * factor)
        w_keep = int(w * factor)
        h_start = (h - h_keep) // 2
        w_start = (w - w_keep) // 2
        crop = grey[h_start : h_start + h_keep, w_start : w_start + w_keep]
        return float(cv2.Laplacian(crop, cv2.CV_64F).var())

    def is_blurry(self, image: np.ndarray, threshold: float | None = None) -> bool:
        """Return ``True`` if *image* is blurry (score below threshold)."""
        t = threshold if threshold is not None else self.threshold
        return self.score(image) < t

    def process(self, record: ImageRecord) -> ImageRecord:
        """Populate *record* blur fields; sets cull_reason if blurry.

        Uses record.thumbnail if available, otherwise raises ValueError.
        """
        from photos_pipeline.modules.ingestion import ImageRecord  # avoid circular import  # noqa: F811, PLC0415

        if record.thumbnail is None:
            raise ValueError(f"No thumbnail available for {record.path}")
        record.blur_score = self.score(record.thumbnail)
        if self.is_blurry(record.thumbnail):
            record.cull_reason = "blur"
        elif record.cull_reason == "blur":
            # Clear stale cull reason from a previous pass
            record.cull_reason = None
        return record
