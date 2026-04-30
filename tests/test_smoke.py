"""Smoke tests for the initial project setup."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from photos_pipeline.cli import main
from photos_pipeline.config import get_settings
from photos_pipeline.modules.ingestion import ImageRecord


def test_cli_help() -> None:
    """The CLI entry point should be discoverable."""
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Automated photo post-processing pipeline." in result.output


def test_settings_defaults() -> None:
    """Default settings should be available without environment variables."""
    settings = get_settings()

    assert settings.app_name == "photos-pipeline"
    assert settings.api_port == 8000


def test_image_record_defaults(sample_workspace: Path) -> None:
    """ImageRecord should capture source paths and empty metadata by default."""
    image_path = sample_workspace / "image.jpg"
    image_path.write_bytes(b"")

    record = ImageRecord(path=image_path, format="jpeg")

    assert record.path == image_path
    assert record.camera_make == ""
    assert record.thumbnail is None


@pytest.mark.unit
def test_subpackages_are_importable() -> None:
    """All module sub-packages should be importable (covers stub __init__ files)."""
    from photos_pipeline import utils  # noqa: F401
    from photos_pipeline.modules import correction, culling, export, scoring  # noqa: F401

    assert isinstance(culling.__all__, list)
    assert isinstance(correction.__all__, list)
    assert isinstance(export.__all__, list)
    assert isinstance(scoring.__all__, list)
    assert isinstance(utils.__all__, list)
