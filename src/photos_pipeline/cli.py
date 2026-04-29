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
@click.argument("input_path", required=False, type=click.Path(path_type=Path))
@click.argument("output_path", required=False, type=click.Path(path_type=Path))
def run(input_path: Path | None, output_path: Path | None) -> None:
    """Run the pipeline scaffold."""
    if input_path is None or output_path is None:
        console.print(
            "Project scaffolding is installed. Full pipeline execution arrives in later specs."
        )
        return

    pipeline = Pipeline()
    raise click.ClickException(
        f"{pipeline.__class__.__name__} is not implemented yet for {input_path} -> {output_path}."
    )
