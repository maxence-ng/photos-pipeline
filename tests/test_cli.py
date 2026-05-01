"""Unit tests for the CLI entry point (SPEC-010)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from photos_pipeline.cli import main
from photos_pipeline.modules.ingestion import ImageRecord
from photos_pipeline.pipeline import CullingSummary, PipelineResult


def _pipeline_result(input_path: Path, output_path: Path) -> PipelineResult:
    return PipelineResult(
        input_path=input_path,
        output_path=output_path,
        total_images=5,
        selected_images=4,
        culled_by_reason={"blur": 1},
        exported_by_format={"jpg": 4},
        exported_files=[output_path / f"photo-{idx}.jpg" for idx in range(4)],
    )


@pytest.mark.unit
def test_process_runs_with_expected_defaults(tmp_path: Path, mocker) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()

    pipeline_instance = mocker.Mock()
    pipeline_instance.run.return_value = _pipeline_result(input_path, output_path)
    pipeline_cls = mocker.patch("photos_pipeline.cli.Pipeline", return_value=pipeline_instance)

    result = CliRunner().invoke(
        main,
        ["process", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    pipeline_cls.assert_called_once()
    assert pipeline_instance.run.call_count == 1
    kwargs = pipeline_instance.run.call_args.kwargs
    assert kwargs["mode"] == "auto"
    assert kwargs["style"] == "natural"
    assert kwargs["no_cull"] is False
    assert kwargs["export_formats"] == ("jpg",)
    assert kwargs["threads"] >= 1
    assert kwargs["blur_threshold"] is None
    assert kwargs["on_culling_complete"] is None
    assert callable(kwargs["progress"])
    assert "Processed: 5" in result.output
    assert "Culled: 1 (blur=1)" in result.output
    assert "Exported: 4 (jpg=4)" in result.output


@pytest.mark.unit
def test_process_passes_manual_mode_callback(tmp_path: Path, mocker) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()

    pipeline_instance = mocker.Mock()

    def _run_side_effect(**kwargs):
        callback = kwargs["on_culling_complete"]
        assert callback is not None
        callback(CullingSummary(total_images=5, selected_images=4, culled_by_reason={"blur": 1}))
        return _pipeline_result(input_path, output_path)

    pipeline_instance.run.side_effect = _run_side_effect
    mocker.patch("photos_pipeline.cli.Pipeline", return_value=pipeline_instance)

    result = CliRunner().invoke(
        main,
        [
            "process",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--mode",
            "manual",
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "Culling complete: kept 4/5, culled 1 (blur=1)." in result.output


@pytest.mark.unit
def test_process_fails_for_unimplemented_export_formats(tmp_path: Path, mocker) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()

    pipeline_cls = mocker.patch("photos_pipeline.cli.Pipeline")

    result = CliRunner().invoke(
        main,
        [
            "process",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--export",
            "png",
        ],
    )

    assert result.exit_code != 0
    assert "not implemented yet" in result.output
    assert "Supported currently: jpg" in result.output
    pipeline_cls.assert_not_called()


@pytest.mark.unit
def test_process_honours_threads_and_blur_threshold(tmp_path: Path, mocker) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()

    pipeline_instance = mocker.Mock()
    pipeline_instance.run.return_value = _pipeline_result(input_path, output_path)
    mocker.patch("photos_pipeline.cli.Pipeline", return_value=pipeline_instance)

    result = CliRunner().invoke(
        main,
        [
            "process",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--threads",
            "3",
            "--blur-threshold",
            "123.5",
            "--no-cull",
            "--style",
            "none",
        ],
    )

    assert result.exit_code == 0
    kwargs = pipeline_instance.run.call_args.kwargs
    assert kwargs["threads"] == 3
    assert kwargs["blur_threshold"] == 123.5
    assert kwargs["no_cull"] is True
    assert kwargs["style"] == "none"


@pytest.mark.unit
def test_ingest_lists_records(tmp_path: Path, mocker) -> None:
    input_path = tmp_path / "input"
    input_path.mkdir()
    first = ImageRecord(path=input_path / "a.jpg", format="jpeg")
    second = ImageRecord(path=input_path / "b.nef", format="raw")
    scan = mocker.patch("photos_pipeline.cli.Ingester.scan", return_value=[first, second])

    result = CliRunner().invoke(main, ["ingest", "--input", str(input_path)])

    assert result.exit_code == 0
    scan.assert_called_once_with(input_path, recursive=False)
    assert "Found 2 supported image(s)" in result.output
    assert first.path.name in result.output
    assert second.path.name in result.output
