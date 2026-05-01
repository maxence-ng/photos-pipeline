"""Unit tests for record-oriented scoring integration."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from photos_pipeline.modules.ingestion import ImageRecord
from photos_pipeline.modules.scoring import ImageRecordScorer


class _FakeAestheticScorer:
    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.batches: list[list[np.ndarray]] = []

    def score(self, image: np.ndarray) -> float:
        return self.score_batch([image])[0]

    def score_batch(self, images: list[np.ndarray]) -> list[float]:
        self.batches.append(images)
        return self._scores[: len(images)]


def _make_record(name: str, *, thumbnail: np.ndarray | None = None) -> ImageRecord:
    return ImageRecord(path=Path(name), format="jpeg", thumbnail=thumbnail)


@pytest.mark.unit
def test_score_batch_persists_scores_on_records() -> None:
    first = _make_record("first.jpg", thumbnail=np.zeros((12, 12, 3), dtype=np.uint8))
    second = _make_record("second.jpg", thumbnail=np.ones((12, 12, 3), dtype=np.uint8))
    backend = _FakeAestheticScorer([6.25, 8.5])

    scores = ImageRecordScorer(scorer=backend).score_batch([first, second])

    assert scores == [6.25, 8.5]
    assert first.aesthetic_score == 6.25
    assert second.aesthetic_score == 8.5
    assert len(backend.batches) == 1
    assert backend.batches[0][0] is first.thumbnail
    assert backend.batches[0][1] is second.thumbnail


@pytest.mark.unit
def test_process_returns_mutated_record() -> None:
    record = _make_record("image.jpg", thumbnail=np.full((16, 16, 3), 128, dtype=np.uint8))
    processor = ImageRecordScorer(scorer=_FakeAestheticScorer([7.0]))

    processed = processor.process(record)

    assert processed is record
    assert record.aesthetic_score == 7.0


@pytest.mark.unit
def test_process_batch_returns_mutated_records(synthetic_thumbnail_factory) -> None:
    first = _make_record("first.jpg", thumbnail=synthetic_thumbnail_factory(32))
    second = _make_record("second.jpg", thumbnail=synthetic_thumbnail_factory(224))
    processor = ImageRecordScorer(scorer=_FakeAestheticScorer([4.0, 9.0]))

    processed = processor.process_batch([first, second])

    assert processed[0] is first
    assert processed[1] is second
    assert first.aesthetic_score == 4.0
    assert second.aesthetic_score == 9.0


@pytest.mark.unit
def test_process_batch_raises_when_thumbnail_missing() -> None:
    ready = _make_record("ready.jpg", thumbnail=np.zeros((8, 8, 3), dtype=np.uint8))
    missing = _make_record("missing.jpg")
    backend = _FakeAestheticScorer([5.0, 6.0])

    with pytest.raises(ValueError, match=re.escape(f"No thumbnail available for {missing.path}")):
        ImageRecordScorer(scorer=backend).process_batch([ready, missing])

    assert ready.aesthetic_score is None
    assert missing.aesthetic_score is None
    assert backend.batches == []


@pytest.mark.unit
def test_score_batch_raises_when_backend_returns_wrong_number_of_scores(
    synthetic_thumbnail_factory,
) -> None:
    first = _make_record("first.jpg", thumbnail=synthetic_thumbnail_factory(64))
    second = _make_record("second.jpg", thumbnail=synthetic_thumbnail_factory(192))
    backend = _FakeAestheticScorer([5.0])

    with pytest.raises(RuntimeError, match="Scorer returned 1 scores for 2 records"):
        ImageRecordScorer(scorer=backend).score_batch([first, second])

    assert first.aesthetic_score is None
    assert second.aesthetic_score is None
    assert len(backend.batches) == 1


@pytest.mark.unit
def test_processor_uses_factory_when_backend_not_supplied(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _FakeAestheticScorer([9.0])
    created: dict[str, bool] = {}

    def fake_create_scorer(*_args: object, **_kwargs: object) -> _FakeAestheticScorer:
        created["called"] = True
        return backend

    monkeypatch.setattr("photos_pipeline.modules.scoring.records.create_scorer", fake_create_scorer)
    record = _make_record("factory.jpg", thumbnail=np.zeros((10, 10, 3), dtype=np.uint8))

    score = ImageRecordScorer().score(record)

    assert score == 9.0
    assert record.aesthetic_score == 9.0
    assert created["called"] is True
