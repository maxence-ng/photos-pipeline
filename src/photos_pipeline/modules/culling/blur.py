"""Blur detection using Laplacian variance."""

from __future__ import annotations

import math

import cv2
import numpy as np

__all__ = ["BlurDetector"]


class BlurDetector:
    """Detect blur via Laplacian variance on a greyscale centre crop."""

    def __init__(self, threshold: float = 100.0) -> None:
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
