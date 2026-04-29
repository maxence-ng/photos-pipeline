"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Provide an empty workspace directory for smoke tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace
