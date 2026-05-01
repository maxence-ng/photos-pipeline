"""Tests for the CLI entry point (SPEC-010 scaffold)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from photos_pipeline.cli import main


@pytest.mark.unit
def test_run_no_args_prints_scaffold_message() -> None:
    """Calling `run` without arguments prints the scaffolding notice."""
    result = CliRunner().invoke(main, ["run"])

    assert result.exit_code == 0
    assert "scaffolding" in result.output.lower() or "pipeline" in result.output.lower()


@pytest.mark.unit
def test_run_with_paths_raises_not_implemented(tmp_path) -> None:
    """Calling `run` with paths reports that the pipeline is not implemented yet."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    result = CliRunner().invoke(main, ["run", str(input_dir), str(output_dir)])

    assert result.exit_code != 0
    assert "defined in later specs" in result.output.lower()


@pytest.mark.unit
def test_run_accepts_style_option(tmp_path) -> None:
    """The run command should accept a named style option."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    result = CliRunner().invoke(
        main,
        ["run", "--style", "cinematic", str(input_dir), str(output_dir)],
    )

    assert result.exit_code != 0
    assert "style=cinematic" in result.output.lower()


@pytest.mark.unit
def test_run_accepts_style_none(tmp_path) -> None:
    """The run command should allow --style none to skip style application."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    result = CliRunner().invoke(
        main,
        ["run", "--style", "none", str(input_dir), str(output_dir)],
    )

    assert result.exit_code != 0
    assert "style=none" in result.output.lower()
