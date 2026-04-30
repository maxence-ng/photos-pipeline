"""Unit tests for the ingestion module (SPEC-002)."""

from __future__ import annotations

import io
import logging
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from photos_pipeline.modules.ingestion import (
    JPEG_EXTENSIONS,
    RAW_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    ImageRecord,
    Ingester,
    _parse_exif_datetime,
    _extract_raw_record,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXIF_DATETIME = "2024:06:15 10:30:00"
_EXPECTED_DT = datetime(2024, 6, 15, 10, 30, 0)


def _make_jpeg(
    path: Path,
    size: tuple[int, int] = (200, 150),
    camera_make: str = "TestMake",
    camera_model: str = "TestModel",
    dt_str: str | None = _EXIF_DATETIME,
) -> None:
    """Write a minimal JPEG with basic EXIF tags to *path*."""
    import piexif

    exif_dict: dict = {"0th": {}, "Exif": {}}
    if camera_make:
        exif_dict["0th"][piexif.ImageIFD.Make] = camera_make.encode()
    if camera_model:
        exif_dict["0th"][piexif.ImageIFD.Model] = camera_model.encode()
    if dt_str:
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
    exif_bytes = piexif.dump(exif_dict)

    img = Image.new("RGB", size, color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    path.write_bytes(buf.getvalue())


def _make_jpeg_no_exif(path: Path, size: tuple[int, int] = (100, 100)) -> None:
    """Write a JPEG without any EXIF data."""
    img = Image.new("RGB", size, color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    path.write_bytes(buf.getvalue())


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_supported_extensions_complete() -> None:
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".jpeg" in SUPPORTED_EXTENSIONS
    for ext in (".orf", ".cr2", ".nef", ".raf", ".arw", ".rw2"):
        assert ext in RAW_EXTENSIONS
    for ext in (".jpg", ".jpeg"):
        assert ext in JPEG_EXTENSIONS


# ---------------------------------------------------------------------------
# ImageRecord construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_image_record_fields() -> None:
    """ImageRecord stores all required fields."""
    path = Path("/fake/image.jpg")
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    record = ImageRecord(
        path=path,
        format="jpeg",
        camera_make="Canon",
        camera_model="EOS R5",
        capture_datetime=_EXPECTED_DT,
        width=800,
        height=600,
        thumbnail=arr,
    )
    assert record.path == path
    assert record.format == "jpeg"
    assert record.camera_make == "Canon"
    assert record.camera_model == "EOS R5"
    assert record.capture_datetime == _EXPECTED_DT
    assert record.width == 800
    assert record.height == 600
    assert record.thumbnail is arr


# ---------------------------------------------------------------------------
# Ingester — basic scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scan_returns_empty_for_empty_dir(tmp_path: Path) -> None:
    ingester = Ingester()
    records = ingester.scan(tmp_path)
    assert records == []


@pytest.mark.unit
def test_scan_raises_for_file_path(tmp_path: Path) -> None:
    f = tmp_path / "file.jpg"
    f.write_bytes(b"")
    with pytest.raises(ValueError, match="directory"):
        Ingester().scan(f)


@pytest.mark.unit
def test_scan_single_jpeg(tmp_path: Path) -> None:
    """A single valid JPEG produces one ImageRecord with correct fields."""
    _make_jpeg(tmp_path / "photo.jpg")
    ingester = Ingester()
    records = ingester.scan(tmp_path)

    assert len(records) == 1
    rec = records[0]
    assert rec.format == "jpeg"
    assert rec.path.name == "photo.jpg"
    assert rec.camera_make == "TestMake"
    assert rec.camera_model == "TestModel"
    assert rec.capture_datetime == _EXPECTED_DT
    assert rec.width == 200
    assert rec.height == 150


@pytest.mark.unit
def test_scan_jpeg_case_insensitive(tmp_path: Path) -> None:
    """Extensions should be matched case-insensitively."""
    _make_jpeg(tmp_path / "photo.JPEG")
    records = Ingester().scan(tmp_path)
    assert len(records) == 1


@pytest.mark.unit
def test_scan_multiple_jpegs(tmp_path: Path) -> None:
    for i in range(3):
        _make_jpeg(tmp_path / f"photo_{i}.jpg")
    records = Ingester().scan(tmp_path)
    assert len(records) == 3


@pytest.mark.unit
def test_scan_skips_unsupported_extension(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Files with unsupported extensions are skipped with a warning."""
    (tmp_path / "video.mp4").write_bytes(b"\x00")
    (tmp_path / "document.txt").write_bytes(b"text")
    _make_jpeg(tmp_path / "ok.jpg")

    with caplog.at_level(logging.WARNING, logger="photos_pipeline.modules.ingestion"):
        records = Ingester().scan(tmp_path)

    assert len(records) == 1
    assert any("mp4" in msg or "Unsupported" in msg for msg in caplog.messages)


@pytest.mark.unit
def test_scan_no_exif_jpeg(tmp_path: Path) -> None:
    """JPEG without EXIF should still produce a record (with empty strings)."""
    _make_jpeg_no_exif(tmp_path / "bare.jpg")
    records = Ingester().scan(tmp_path)
    assert len(records) == 1
    rec = records[0]
    assert rec.format == "jpeg"
    assert rec.camera_make == ""
    assert rec.capture_datetime is None


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_thumbnail_capped_at_800(tmp_path: Path) -> None:
    """Thumbnails for large images must not exceed 800 px on either axis."""
    _make_jpeg(tmp_path / "big.jpg", size=(3000, 2000))
    records = Ingester().scan(tmp_path)
    assert len(records) == 1
    thumb = records[0].thumbnail
    assert thumb is not None
    h, w = thumb.shape[:2]
    assert w <= 800
    assert h <= 800


@pytest.mark.unit
def test_thumbnail_small_image_not_upscaled(tmp_path: Path) -> None:
    """Images smaller than 800×800 should not be upscaled."""
    _make_jpeg(tmp_path / "small.jpg", size=(100, 80))
    records = Ingester().scan(tmp_path)
    thumb = records[0].thumbnail
    assert thumb is not None
    h, w = thumb.shape[:2]
    assert w == 100
    assert h == 80


@pytest.mark.unit
def test_thumbnail_is_rgb(tmp_path: Path) -> None:
    """Thumbnails must be RGB numpy arrays (3 channels)."""
    _make_jpeg(tmp_path / "photo.jpg", size=(200, 150))
    records = Ingester().scan(tmp_path)
    thumb = records[0].thumbnail
    assert thumb is not None
    assert thumb.ndim == 3
    assert thumb.shape[2] == 3


# ---------------------------------------------------------------------------
# Recursive scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scan_non_recursive_ignores_subdirs(tmp_path: Path) -> None:
    """Non-recursive scan must not descend into sub-directories."""
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_jpeg(sub / "nested.jpg")
    _make_jpeg(tmp_path / "top.jpg")

    records = Ingester().scan(tmp_path, recursive=False)
    assert len(records) == 1
    assert records[0].path.name == "top.jpg"


@pytest.mark.unit
def test_scan_recursive_finds_all(tmp_path: Path) -> None:
    """Recursive scan must find images in all nested sub-directories."""
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    _make_jpeg(tmp_path / "a.jpg")
    _make_jpeg(sub / "b.jpg")

    records = Ingester().scan(tmp_path, recursive=True)
    names = {r.path.name for r in records}
    assert names == {"a.jpg", "b.jpg"}


# ---------------------------------------------------------------------------
# _parse_exif_datetime — exception branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_exif_datetime_valid() -> None:
    assert _parse_exif_datetime("2024:06:15 10:30:00") == datetime(2024, 6, 15, 10, 30, 0)


@pytest.mark.unit
def test_parse_exif_datetime_invalid_returns_none() -> None:
    """Malformed datetime string should return None without raising."""
    assert _parse_exif_datetime("not-a-date") is None
    assert _parse_exif_datetime("") is None


# ---------------------------------------------------------------------------
# scan() — exception paths (JPEG and RAW)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scan_jpeg_exception_is_skipped(tmp_path: Path, mocker) -> None:
    """If _extract_jpeg_record raises, the file is skipped with a warning."""
    _make_jpeg(tmp_path / "bad.jpg")
    mocker.patch(
        "photos_pipeline.modules.ingestion._extract_jpeg_record",
        side_effect=OSError("simulated read error"),
    )
    records = Ingester().scan(tmp_path)
    assert records == []


@pytest.mark.unit
def test_scan_raw_exception_is_skipped(tmp_path: Path, mocker) -> None:
    """If _extract_raw_record raises, the file is skipped with a warning."""
    (tmp_path / "photo.nef").write_bytes(b"fake raw")
    mocker.patch(
        "photos_pipeline.modules.ingestion._extract_raw_record",
        side_effect=RuntimeError("simulated raw error"),
    )
    records = Ingester().scan(tmp_path)
    assert records == []


# ---------------------------------------------------------------------------
# _extract_raw_record — mocked rawpy paths
# ---------------------------------------------------------------------------


def _make_rawpy_mock(thumb_format: str = "jpeg") -> MagicMock:
    """Build a minimal rawpy mock with a configurable thumbnail format."""

    class _FakeNoThumbnailError(Exception):
        pass

    mock_rawpy = MagicMock()
    mock_rawpy.LibRawNoThumbnailError = _FakeNoThumbnailError

    mock_raw = MagicMock()
    mock_raw.sizes.width = 4000
    mock_raw.sizes.height = 3000

    if thumb_format == "jpeg":
        buf = io.BytesIO()
        Image.new("RGB", (400, 300)).save(buf, format="JPEG")
        mock_thumb = MagicMock()
        mock_thumb.format = mock_rawpy.ThumbFormat.JPEG
        mock_thumb.data = buf.getvalue()
        mock_raw.extract_thumb.return_value = mock_thumb
    elif thumb_format == "bitmap":
        mock_thumb = MagicMock()
        mock_thumb.format = mock_rawpy.ThumbFormat.BITMAP
        mock_thumb.data = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_raw.extract_thumb.return_value = mock_thumb
    elif thumb_format == "none":
        mock_raw.extract_thumb.side_effect = _FakeNoThumbnailError("no thumb")

    mock_rawpy.imread.return_value.__enter__ = lambda _self: mock_raw
    mock_rawpy.imread.return_value.__exit__ = MagicMock(return_value=False)

    return mock_rawpy


@pytest.mark.unit
def test_extract_raw_record_jpeg_thumb(tmp_path: Path, monkeypatch) -> None:
    """_extract_raw_record returns a record with thumbnail when rawpy yields a JPEG thumb."""
    raw_path = tmp_path / "photo.nef"
    raw_path.write_bytes(b"fake raw content")

    mock_rawpy = _make_rawpy_mock("jpeg")
    monkeypatch.setitem(sys.modules, "rawpy", mock_rawpy)

    record = _extract_raw_record(raw_path)

    assert record.format == "raw"
    assert record.width == 4000
    assert record.height == 3000
    assert record.thumbnail is not None
    assert record.thumbnail.shape[2] == 3


@pytest.mark.unit
def test_extract_raw_record_bitmap_thumb(tmp_path: Path, monkeypatch) -> None:
    """_extract_raw_record handles a BITMAP thumbnail from rawpy."""
    raw_path = tmp_path / "photo.orf"
    raw_path.write_bytes(b"fake raw content")

    mock_rawpy = _make_rawpy_mock("bitmap")
    monkeypatch.setitem(sys.modules, "rawpy", mock_rawpy)

    record = _extract_raw_record(raw_path)

    assert record.thumbnail is not None


@pytest.mark.unit
def test_extract_raw_record_no_thumb(tmp_path: Path, monkeypatch) -> None:
    """_extract_raw_record returns a record with thumbnail=None when rawpy has no thumb."""
    raw_path = tmp_path / "photo.cr2"
    raw_path.write_bytes(b"fake raw content")

    mock_rawpy = _make_rawpy_mock("none")
    monkeypatch.setitem(sys.modules, "rawpy", mock_rawpy)

    record = _extract_raw_record(raw_path)

    assert record.thumbnail is None
    assert record.width == 4000


@pytest.mark.unit
def test_extract_raw_record_rawpy_open_fails(tmp_path: Path, monkeypatch) -> None:
    """_extract_raw_record returns an empty record when rawpy.imread raises."""
    raw_path = tmp_path / "photo.arw"
    raw_path.write_bytes(b"not a raw file")

    mock_rawpy = MagicMock()
    mock_rawpy.imread.side_effect = Exception("not a RAW file")
    monkeypatch.setitem(sys.modules, "rawpy", mock_rawpy)

    record = _extract_raw_record(raw_path)

    assert record.format == "raw"
    assert record.width == 0
    assert record.thumbnail is None


@pytest.mark.unit
def test_scan_raw_file_produces_record(tmp_path: Path, monkeypatch) -> None:
    """scan() calls _extract_raw_record for RAW extensions and includes the result."""
    raw_path = tmp_path / "shot.nef"
    raw_path.write_bytes(b"fake raw content")

    mock_rawpy = _make_rawpy_mock("jpeg")
    monkeypatch.setitem(sys.modules, "rawpy", mock_rawpy)

    records = Ingester().scan(tmp_path)

    assert len(records) == 1
    assert records[0].format == "raw"
    assert records[0].path == raw_path

