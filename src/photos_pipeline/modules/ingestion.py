"""Ingestion module stubs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ImageRecord", "IngestionModule"]


@dataclass(slots=True)
class ImageRecord:
    """Minimal image record shared across pipeline stages."""

    source_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    thumbnail_path: Path | None = None


class IngestionModule:
    """Placeholder ingestion module."""

    def scan(self, input_path: Path) -> list[ImageRecord]:
        """Scan an input folder and return discovered records."""
        raise NotImplementedError(f"Ingestion scanning is not implemented yet for {input_path}.")
