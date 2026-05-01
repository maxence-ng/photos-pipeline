"""Record-oriented scoring APIs built on top of scoring backends."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from photos_pipeline.config import Settings
from photos_pipeline.modules.scoring.backend import AestheticScorer, ClipBackend, create_scorer

if TYPE_CHECKING:
    import numpy as np

    from photos_pipeline.modules.ingestion import ImageRecord

__all__ = ["ImageRecordScorer"]


class ImageRecordScorer:
    """Score ``ImageRecord`` thumbnails and persist the results on each record."""

    def __init__(
        self,
        *,
        scorer: AestheticScorer | None = None,
        settings: Settings | None = None,
        clip_backend: ClipBackend | None = None,
    ) -> None:
        self._scorer = scorer or create_scorer(settings, clip_backend=clip_backend)

    def score(self, record: ImageRecord) -> float:
        """Score a single record thumbnail and store the result on the record."""
        return self.score_batch([record])[0]

    def process(self, record: ImageRecord) -> ImageRecord:
        """Populate ``record.aesthetic_score`` and return the same record."""
        self.score(record)
        return record

    def score_batch(self, records: Sequence[ImageRecord]) -> list[float]:
        """Score *records* in one backend call and persist each score."""
        record_list = list(records)
        if not record_list:
            return []

        thumbnails = [self._require_thumbnail(record) for record in record_list]
        scores = self._scorer.score_batch(thumbnails)

        if len(scores) != len(record_list):
            raise RuntimeError(
                f"Scorer returned {len(scores)} scores for {len(record_list)} records."
            )

        for record, score in zip(record_list, scores, strict=True):
            record.aesthetic_score = score

        return scores

    def process_batch(self, records: Sequence[ImageRecord]) -> list[ImageRecord]:
        """Populate aesthetic scores for *records* and return the same records."""
        record_list = list(records)
        self.score_batch(record_list)
        return record_list

    @staticmethod
    def _require_thumbnail(record: ImageRecord) -> np.ndarray:
        if record.thumbnail is None:
            raise ValueError(f"No thumbnail available for {record.path}")
        return record.thumbnail
