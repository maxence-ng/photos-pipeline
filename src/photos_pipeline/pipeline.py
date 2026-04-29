"""Shared pipeline orchestration primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Pipeline", "PipelineResult"]


@dataclass(slots=True)
class PipelineResult:
    """Result placeholder for future pipeline runs."""

    input_path: Path
    output_path: Path
    processed_files: list[Path] = field(default_factory=list)


class Pipeline:
    """Top-level orchestrator stub shared by CLI and API layers."""

    def run(self, input_path: Path, output_path: Path) -> PipelineResult:
        """Run the photo pipeline."""
        raise NotImplementedError(
            f"Pipeline execution is defined in later specs: {input_path} -> {output_path}."
        )
