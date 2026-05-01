"""Command-line entry points for the photos pipeline."""

from __future__ import annotations

import os
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import TypeVar

import click
from rich.console import Console
from rich.progress import track

from photos_pipeline import __version__
from photos_pipeline.modules.ingestion import Ingester
from photos_pipeline.pipeline import CullingSummary, Pipeline, PipelineError, PipelineResult

console = Console()

__all__ = ["main"]

T = TypeVar("T")
SUPPORTED_EXPORT_CHOICES: tuple[str, ...] = ("jpg", "png", "tiff")
CURRENT_EXPORT_SUPPORT: tuple[str, ...] = ("jpg",)


def _resolve_version() -> str:
    try:
        return package_version("photos-pipeline")
    except PackageNotFoundError:
        return __version__


@click.group(help="Automated photo post-processing pipeline.")
@click.version_option(version=_resolve_version(), prog_name="photos-pipeline")
def main() -> None:
    """Run the CLI."""


@main.command("process")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Input directory containing RAW/JPEG photos.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Output directory for processed exports.",
)
@click.option(
    "--mode",
    type=click.Choice(["auto", "manual"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Processing mode; manual pauses after culling.",
)
@click.option(
    "--style",
    default="natural",
    show_default=True,
    help="Style preset name to apply. Use 'none' to skip style application.",
)
@click.option(
    "--no-cull",
    is_flag=True,
    help="Skip the culling stage.",
)
@click.option(
    "--export",
    "export_formats",
    multiple=True,
    default=("jpg",),
    type=click.Choice(SUPPORTED_EXPORT_CHOICES, case_sensitive=False),
    show_default=True,
    help="Output format(s) to export.",
)
@click.option(
    "--threads",
    type=click.IntRange(min=1),
    default=None,
    help="Worker threads for correction/export (defaults to cpu_count // 2).",
)
@click.option(
    "--blur-threshold",
    type=click.FloatRange(min=0.0, min_open=True),
    default=None,
    help="Override blur-detection threshold for this run.",
)
def process_command(
    input_path: Path,
    output_path: Path,
    mode: str,
    style: str,
    no_cull: bool,
    export_formats: tuple[str, ...],
    threads: int | None,
    blur_threshold: float | None,
) -> None:
    """Run the full processing pipeline."""
    normalised_style = style.strip().lower()
    if not normalised_style:
        raise click.ClickException("--style cannot be empty.")

    selected_export_formats = tuple(fmt.lower() for fmt in export_formats)
    unsupported = sorted(set(selected_export_formats) - set(CURRENT_EXPORT_SUPPORT))
    if unsupported:
        raise click.ClickException(
            "The following export formats are not implemented yet: "
            f"{', '.join(unsupported)}. Supported currently: {', '.join(CURRENT_EXPORT_SUPPORT)}."
        )

    resolved_threads = threads if threads is not None else _default_threads()
    culling_callback = _manual_culling_pause if mode.lower() == "manual" else None
    pipeline = Pipeline()

    try:
        result = pipeline.run(
            input_path=input_path,
            output_path=output_path,
            mode=mode,
            no_cull=no_cull,
            style=normalised_style,
            export_formats=selected_export_formats,
            threads=resolved_threads,
            blur_threshold=blur_threshold,
            on_culling_complete=culling_callback,
            progress=_rich_progress,
        )
    except (PipelineError, ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    _print_summary(result)


@main.command("ingest")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Input directory to scan.",
)
@click.option(
    "--recursive",
    is_flag=True,
    help="Scan sub-directories recursively.",
)
def ingest_command(input_path: Path, recursive: bool) -> None:
    """Preview ingestion candidates without processing."""
    records = Ingester().scan(input_path, recursive=recursive)
    console.print(f"Found {len(records)} supported image(s) in {input_path}.")
    for record in records:
        console.print(str(record.path))


def _manual_culling_pause(summary: CullingSummary) -> None:
    culled_details = _format_reason_counts(summary.culled_by_reason)
    console.print(
        "Culling complete: "
        f"kept {summary.selected_images}/{summary.total_images}, "
        f"culled {summary.culled_images} ({culled_details})."
    )
    click.confirm(
        "Manual mode is paused after culling. Continue with correction/export?",
        default=True,
        abort=True,
    )


def _print_summary(result: PipelineResult) -> None:
    culled_details = _format_reason_counts(result.culled_by_reason)
    exported_details = _format_reason_counts(result.exported_by_format)
    console.print(f"Processed: {result.total_images}")
    console.print(f"Culled: {result.culled_images} ({culled_details})")
    console.print(f"Exported: {result.exported_images} ({exported_details})")


def _format_reason_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{reason}={count}" for reason, count in sorted(counts.items()))


def _rich_progress(
    iterable: Iterable[T],
    description: str,
    total: int | None,
) -> Iterable[T]:
    return track(iterable, description=description, total=total)


def _default_threads() -> int:
    cpu_count = os.cpu_count() or 2
    return max(1, cpu_count // 2)
