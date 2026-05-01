"""Unit tests for pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from photos_pipeline.modules.ingestion import ImageRecord
from photos_pipeline.pipeline import Pipeline


class _StubIngester:
    def __init__(self, records: list[ImageRecord]) -> None:
        self._records = records

    def scan(self, _input_path: Path) -> list[ImageRecord]:
        return self._records


class _StubPresetManager:
    def apply(self, record: ImageRecord, _style: str) -> Path:
        return record.path


class _StubDuplicateDetector:
    def process(self, records: list[ImageRecord]) -> list[object]:
        if len(records) > 1:
            records[-1].cull_reason = "duplicate"
        return []


class _StubBurstGrouper:
    def group(self, _records: list[ImageRecord]) -> list[object]:
        return []


class _StubBurstSelector:
    def select_best(self, _group: object) -> None:
        return None


class _StubBlurDetector:
    def process(self, record: ImageRecord) -> ImageRecord:
        if record.path.name.startswith("blur-"):
            record.cull_reason = "blur"
        record.blur_score = 42.0
        return record


def _blur_factory(_threshold: float | None) -> _StubBlurDetector:
    return _StubBlurDetector()


def _write_jpeg(path: Path) -> None:
    Image.new("RGB", (16, 16), color=(128, 64, 32)).save(path, format="JPEG")


def _record(path: Path) -> ImageRecord:
    return ImageRecord(
        path=path,
        format="jpeg",
        thumbnail=np.zeros((32, 32, 3), dtype=np.uint8),
    )


@pytest.mark.unit
def test_run_exports_without_culling(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()
    output_path.mkdir()

    source = input_path / "photo.jpg"
    _write_jpeg(source)
    records = [_record(source)]

    pipeline = Pipeline(
        ingester=_StubIngester(records),
        preset_manager=_StubPresetManager(),
        duplicate_detector=_StubDuplicateDetector(),
        burst_grouper=_StubBurstGrouper(),
        burst_selector=_StubBurstSelector(),
        blur_detector_factory=_blur_factory,
    )

    result = pipeline.run(
        input_path=input_path,
        output_path=output_path,
        no_cull=True,
        style=None,
        export_formats=("jpg",),
        threads=1,
    )

    assert result.total_images == 1
    assert result.selected_images == 1
    assert result.culled_images == 0
    assert result.exported_by_format == {"jpg": 1}
    assert result.exported_images == 1
    assert (output_path / "photo.jpg").exists()


@pytest.mark.unit
def test_run_culls_and_invokes_manual_callback(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()
    output_path.mkdir()

    keep_path = input_path / "keep.jpg"
    blur_path = input_path / "blur-shot.jpg"
    duplicate_path = input_path / "duplicate.jpg"
    _write_jpeg(keep_path)
    _write_jpeg(blur_path)
    _write_jpeg(duplicate_path)

    records = [_record(blur_path), _record(keep_path), _record(duplicate_path)]
    summaries = []

    pipeline = Pipeline(
        ingester=_StubIngester(records),
        preset_manager=_StubPresetManager(),
        duplicate_detector=_StubDuplicateDetector(),
        burst_grouper=_StubBurstGrouper(),
        burst_selector=_StubBurstSelector(),
        blur_detector_factory=_blur_factory,
    )

    result = pipeline.run(
        input_path=input_path,
        output_path=output_path,
        mode="manual",
        style=None,
        export_formats=("jpg",),
        threads=1,
        on_culling_complete=summaries.append,
    )

    assert len(summaries) == 1
    assert summaries[0].total_images == 3
    assert summaries[0].selected_images == 1
    assert summaries[0].culled_by_reason == {"blur": 1, "duplicate": 1}
    assert result.selected_images == 1
    assert result.culled_by_reason == {"blur": 1, "duplicate": 1}
    assert result.exported_images == 1
    assert (output_path / "keep.jpg").exists()


@pytest.mark.unit
def test_run_rejects_unsupported_export_format(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()

    source = input_path / "photo.jpg"
    _write_jpeg(source)
    records = [_record(source)]

    pipeline = Pipeline(
        ingester=_StubIngester(records),
        preset_manager=_StubPresetManager(),
        blur_detector_factory=_blur_factory,
    )

    with pytest.raises(ValueError, match="Unsupported export formats"):
        pipeline.run(
            input_path=input_path,
            output_path=output_path,
            no_cull=True,
            style=None,
            export_formats=("png",),
            threads=1,
        )


@pytest.mark.unit
def test_run_rejects_manual_mode_without_callback(tmp_path: Path) -> None:
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    input_path.mkdir()

    source = input_path / "photo.jpg"
    _write_jpeg(source)
    records = [_record(source)]

    pipeline = Pipeline(
        ingester=_StubIngester(records),
        preset_manager=_StubPresetManager(),
        blur_detector_factory=_blur_factory,
    )

    with pytest.raises(ValueError, match="on_culling_complete"):
        pipeline.run(
            input_path=input_path,
            output_path=output_path,
            mode="manual",
            no_cull=True,
            style=None,
            export_formats=("jpg",),
            threads=1,
        )
