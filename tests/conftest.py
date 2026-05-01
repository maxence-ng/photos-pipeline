"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest


@dataclass(frozen=True)
class SyntheticScoringReference:
    """Synthetic image and expected deterministic score for scoring tests."""

    name: str
    image: np.ndarray
    expected_clip_score: float


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Provide an empty workspace directory for smoke tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def _make_uniform_rgb_image(pixel_value: int, *, size: int = 32) -> np.ndarray:
    return np.full((size, size, 3), pixel_value, dtype=np.uint8)


@pytest.fixture
def synthetic_thumbnail_factory() -> Callable[[int], np.ndarray]:
    """Build deterministic synthetic RGB thumbnails for unit tests."""

    def factory(pixel_value: int) -> np.ndarray:
        return _make_uniform_rgb_image(pixel_value)

    return factory


@pytest.fixture
def synthetic_scoring_references(
    synthetic_thumbnail_factory: Callable[[int], np.ndarray],
) -> tuple[SyntheticScoringReference, ...]:
    """Provide stable synthetic reference images for deterministic scoring checks."""

    return (
        SyntheticScoringReference(
            name="dark",
            image=synthetic_thumbnail_factory(0),
            expected_clip_score=1.060235619544983,
        ),
        SyntheticScoringReference(
            name="neutral",
            image=synthetic_thumbnail_factory(128),
            expected_clip_score=5.544116973876953,
        ),
        SyntheticScoringReference(
            name="bright",
            image=synthetic_thumbnail_factory(255),
            expected_clip_score=9.939764976501465,
        ),
    )
