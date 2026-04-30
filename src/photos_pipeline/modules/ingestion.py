"""Ingestion module — scans input folders and produces ImageRecord objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import exifread
import numpy as np
from PIL import Image

__all__ = ["ImageRecord", "Ingester", "IngestionModule"]

logger = logging.getLogger(__name__)

RAW_EXTENSIONS: frozenset[str] = frozenset(
    {".orf", ".cr2", ".nef", ".raf", ".arw", ".rw2"}
)
JPEG_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg"})
SUPPORTED_EXTENSIONS: frozenset[str] = RAW_EXTENSIONS | JPEG_EXTENSIONS


@dataclass(slots=True)
class ImageRecord:
    """Represents a single image as it passes through the pipeline."""

    path: Path
    format: Literal["raw", "jpeg"]
    camera_make: str = ""
    camera_model: str = ""
    capture_datetime: datetime | None = None
    width: int = 0
    height: int = 0
    thumbnail: np.ndarray | None = field(default=None, repr=False)
    blur_score: float | None = field(default=None)
    cull_reason: str | None = field(default=None)

    # Legacy alias kept for backward compatibility with early smoke tests
    @property
    def source_path(self) -> Path:  # pragma: no cover
        return self.path

    @property
    def metadata(self) -> dict[str, str]:  # pragma: no cover
        return {
            "camera_make": self.camera_make,
            "camera_model": self.camera_model,
        }

    @property
    def thumbnail_path(self) -> Path | None:  # pragma: no cover
        return None


def _parse_exif_datetime(value: str) -> datetime | None:
    """Parse an EXIF datetime string (``YYYY:MM:DD HH:MM:SS``)."""
    try:
        return datetime.strptime(value.strip(), "%Y:%m:%d %H:%M:%S")
    except (ValueError, AttributeError):
        return None


def _extract_jpeg_record(path: Path) -> ImageRecord:
    """Build an ImageRecord for a JPEG file."""
    camera_make = ""
    camera_model = ""
    capture_datetime: datetime | None = None

    with path.open("rb") as fh:
        tags = exifread.process_file(fh, stop_tag="EXIF DateTimeOriginal", details=False)

    camera_make = str(tags.get("Image Make", "")).strip()
    camera_model = str(tags.get("Image Model", "")).strip()
    dt_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
    if dt_tag:
        capture_datetime = _parse_exif_datetime(str(dt_tag))

    with Image.open(path) as img:
        width, height = img.size
        img.thumbnail((800, 800))
        thumbnail = np.array(img.convert("RGB"))

    return ImageRecord(
        path=path,
        format="jpeg",
        camera_make=camera_make,
        camera_model=camera_model,
        capture_datetime=capture_datetime,
        width=width,
        height=height,
        thumbnail=thumbnail,
    )


def _extract_raw_record(path: Path) -> ImageRecord:
    """Build an ImageRecord for a RAW file."""
    import rawpy  # lazy import — not available in all environments

    camera_make = ""
    camera_model = ""
    capture_datetime: datetime | None = None
    width = 0
    height = 0
    thumbnail: np.ndarray | None = None

    with path.open("rb") as fh:
        tags = exifread.process_file(fh, stop_tag="EXIF DateTimeOriginal", details=False)

    camera_make = str(tags.get("Image Make", "")).strip()
    camera_model = str(tags.get("Image Model", "")).strip()
    dt_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
    if dt_tag:
        capture_datetime = _parse_exif_datetime(str(dt_tag))

    try:
        with rawpy.imread(str(path)) as raw:
            width = raw.sizes.width
            height = raw.sizes.height
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    import io

                    with Image.open(io.BytesIO(thumb.data)) as img:
                        img.thumbnail((800, 800))
                        thumbnail = np.array(img.convert("RGB"))
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    pil_img = Image.fromarray(thumb.data)
                    pil_img.thumbnail((800, 800))
                    thumbnail = np.array(pil_img.convert("RGB"))
            except rawpy.LibRawNoThumbnailError:
                logger.debug("No embedded thumbnail in %s", path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not open RAW file %s: %s", path.name, exc)
        raise

    return ImageRecord(
        path=path,
        format="raw",
        camera_make=camera_make,
        camera_model=camera_model,
        capture_datetime=capture_datetime,
        width=width,
        height=height,
        thumbnail=thumbnail,
    )


class Ingester:
    """Scans an input directory and returns a list of :class:`ImageRecord` objects."""

    def scan(self, input_path: Path, *, recursive: bool = False) -> list[ImageRecord]:
        """Scan *input_path* and return records for every supported image.

        Args:
            input_path: Directory to scan.
            recursive: When ``True``, descend into sub-directories.

        Returns:
            Ordered list of :class:`ImageRecord` objects (one per supported file).
        """
        if not input_path.is_dir():
            raise ValueError(f"input_path must be a directory, got: {input_path}")

        glob_pattern = "**/*" if recursive else "*"
        records: list[ImageRecord] = []

        for file_path in sorted(input_path.glob(glob_pattern)):
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext in JPEG_EXTENSIONS:
                try:
                    records.append(_extract_jpeg_record(file_path))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Skipping %s: %s", file_path.name, exc)
            elif ext in RAW_EXTENSIONS:
                try:
                    records.append(_extract_raw_record(file_path))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Skipping %s: %s", file_path.name, exc)
            else:
                logger.warning("Unsupported file extension, skipping: %s", file_path.name)

        return records


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------
IngestionModule = Ingester

