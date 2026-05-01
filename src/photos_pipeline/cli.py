"""Command-line entry points for the photos pipeline."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from photos_pipeline.pipeline import Pipeline

console = Console()

__all__ = ["main"]


@click.group(help="Automated photo post-processing pipeline.")
def main() -> None:
    """Run the CLI."""


@main.command()
@click.option(
    "--style",
    default="natural",
    show_default=True,
    help="Style preset name to apply. Use 'none' to skip style application.",
)
@click.argument("input_path", required=False, type=click.Path(path_type=Path))
@click.argument("output_path", required=False, type=click.Path(path_type=Path))
def run(style: str, input_path: Path | None, output_path: Path | None) -> None:
    """Run the pipeline scaffold."""
    if input_path is None or output_path is None:
        console.print(
            "Project scaffolding is installed. Full pipeline execution arrives in later specs."
        )
        return

    normalised_style = style.strip().lower()
    if not normalised_style:
        raise click.ClickException("--style cannot be empty.")

    selected_style = None if normalised_style == "none" else normalised_style
    pipeline = Pipeline()
    try:
        pipeline.run(input_path, output_path, style=selected_style)
    except NotImplementedError as exc:
        raise click.ClickException(str(exc)) from exc
