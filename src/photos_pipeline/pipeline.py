"""Shared pipeline orchestration primitives."""

from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar, cast

from PIL import Image, UnidentifiedImageError

from photos_pipeline.modules.correction import (
    DarktableError,
    PresetError,
    PresetManager,
)
from photos_pipeline.modules.culling import (
    BlurDetector,
    BurstGrouper,
    BurstSelector,
    DuplicateDetector,
)
from photos_pipeline.modules.ingestion import ImageRecord, Ingester

__all__ = ["CullingSummary", "Pipeline", "PipelineError", "PipelineResult"]

T = TypeVar("T")

SUPPORTED_EXPORT_FORMATS: tuple[str, ...] = ("jpg",)


class PipelineError(RuntimeError):
    """Raised when orchestration fails."""


@dataclass(slots=True)
class PipelineResult:
    """Summary of a completed pipeline run."""

    input_path: Path
    output_path: Path
    total_images: int
    selected_images: int
    culled_by_reason: dict[str, int] = field(default_factory=dict)
    exported_by_format: dict[str, int] = field(default_factory=dict)
    exported_files: list[Path] = field(default_factory=list)

    @property
    def culled_images(self) -> int:
        """Return the number of images removed during culling."""
        return sum(self.culled_by_reason.values())

    @property
    def exported_images(self) -> int:
        """Return the number of files written by the export stage."""
        return len(self.exported_files)


@dataclass(slots=True, frozen=True)
class CullingSummary:
    """Summary emitted after culling and before correction/export."""

    total_images: int
    selected_images: int
    culled_by_reason: dict[str, int]

    @property
    def culled_images(self) -> int:
        """Return the number of images removed during culling."""
        return sum(self.culled_by_reason.values())


ProgressCallback = Callable[[Iterable[T], str, int | None], Iterable[T]]
CullingCallback = Callable[[CullingSummary], None]


class Pipeline:
    """Top-level orchestrator shared by CLI and API layers."""

    def __init__(
        self,
        *,
        ingester: Ingester | None = None,
        preset_manager: PresetManager | None = None,
        duplicate_detector: DuplicateDetector | None = None,
        burst_grouper: BurstGrouper | None = None,
        burst_selector: BurstSelector | None = None,
        blur_detector_factory: Callable[[float | None], BlurDetector] | None = None,
    ) -> None:
        self._ingester = ingester or Ingester()
        self._preset_manager = preset_manager or PresetManager()
        self._duplicate_detector = duplicate_detector or DuplicateDetector()
        self._burst_grouper = burst_grouper or BurstGrouper()
        self._burst_selector = burst_selector or BurstSelector()
        self._blur_detector_factory = blur_detector_factory or BlurDetector

    def run(
        self,
        input_path: Path,
        output_path: Path,
        *,
        mode: str = "auto",
        no_cull: bool = False,
        style: str | None = "natural",
        export_formats: tuple[str, ...] = ("jpg",),
        threads: int | None = None,
        blur_threshold: float | None = None,
        on_culling_complete: CullingCallback | None = None,
        progress: ProgressCallback[T] | None = None,
    ) -> PipelineResult:
        """Run the photo pipeline."""
        normalised_mode = mode.strip().lower()
        if normalised_mode not in {"auto", "manual"}:
            raise ValueError(f"Unsupported mode: {mode!r}. Use 'auto' or 'manual'.")

        if threads is None:
            threads = _default_threads()
        if threads < 1:
            raise ValueError("--threads must be >= 1.")

        normalised_style = _normalise_style(style)
        normalised_exports = _normalise_export_formats(export_formats)

        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        records = self._ingester.scan(input_path)
        selected_records = list(records)
        culled_by_reason: dict[str, int] = {}

        if not no_cull:
            blur_detector = self._blur_detector_factory(blur_threshold)
            selected_records = self._apply_culling(records, blur_detector)
            culled_by_reason = dict(
                sorted(
                    Counter(record.cull_reason for record in records if record.cull_reason).items()
                )
            )

        culling_summary = CullingSummary(
            total_images=len(records),
            selected_images=len(selected_records),
            culled_by_reason=culled_by_reason,
        )

        if normalised_mode == "manual":
            if on_culling_complete is None:
                raise ValueError("mode='manual' requires an on_culling_complete callback.")
            on_culling_complete(culling_summary)

        exported_files, exported_by_format = self._export_records(
            selected_records=selected_records,
            output_path=output_path,
            style=normalised_style,
            export_formats=normalised_exports,
            threads=threads,
            progress=progress,
        )

        return PipelineResult(
            input_path=input_path,
            output_path=output_path,
            total_images=len(records),
            selected_images=len(selected_records),
            culled_by_reason=culled_by_reason,
            exported_by_format=exported_by_format,
            exported_files=exported_files,
        )

    def _apply_culling(
        self,
        records: list[ImageRecord],
        blur_detector: BlurDetector,
    ) -> list[ImageRecord]:
        for record in records:
            if record.thumbnail is None:
                record.cull_reason = "missing_thumbnail"
                continue
            blur_detector.process(record)

        duplicate_candidates = [
            record for record in records if record.thumbnail is not None and record.cull_reason is None
        ]
        self._duplicate_detector.process(duplicate_candidates)

        burst_candidates = [record for record in duplicate_candidates if record.cull_reason is None]
        for group in self._burst_grouper.group(burst_candidates):
            self._burst_selector.select_best(group)

        return [record for record in records if record.cull_reason is None]

    def _export_records(
        self,
        *,
        selected_records: list[ImageRecord],
        output_path: Path,
        style: str | None,
        export_formats: tuple[str, ...],
        threads: int,
        progress: ProgressCallback[T] | None,
    ) -> tuple[list[Path], dict[str, int]]:
        exported_files: list[Path] = []
        exported_by_format: Counter[str] = Counter()

        if not selected_records:
            return exported_files, {}

        if threads == 1:
            image_progress = cast(
                Callable[[Iterable[ImageRecord], str, int | None], Iterable[ImageRecord]] | None,
                progress,
            )
            for record in self._with_progress(
                selected_records,
                description="Processing images",
                total=len(selected_records),
                progress=image_progress,
            ):
                outputs = self._process_record(
                    record=record,
                    output_path=output_path,
                    style=style,
                    export_formats=export_formats,
                )
                exported_files.extend(outputs)
                for output_file in outputs:
                    exported_by_format[output_file.suffix.lstrip(".").lower()] += 1
            return exported_files, dict(sorted(exported_by_format.items()))

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(
                    self._process_record,
                    record=record,
                    output_path=output_path,
                    style=style,
                    export_formats=export_formats,
                )
                for record in selected_records
            ]
            future_progress = cast(
                Callable[
                    [Iterable[Future[list[Path]]], str, int | None],
                    Iterable[Future[list[Path]]],
                ]
                | None,
                progress,
            )
            for future in self._with_progress(
                as_completed(futures),
                description="Processing images",
                total=len(futures),
                progress=future_progress,
            ):
                outputs = future.result()
                exported_files.extend(outputs)
                for output_file in outputs:
                    exported_by_format[output_file.suffix.lstrip(".").lower()] += 1

        return exported_files, dict(sorted(exported_by_format.items()))

    def _process_record(
        self,
        *,
        record: ImageRecord,
        output_path: Path,
        style: str | None,
        export_formats: tuple[str, ...],
    ) -> list[Path]:
        source_path = record.path
        if style is not None:
            try:
                source_path = self._preset_manager.apply(record, style)
            except (PresetError, DarktableError) as exc:
                raise PipelineError(f"Failed to apply style {style!r} to {record.path}: {exc}") from exc

        output_files: list[Path] = []
        for export_format in export_formats:
            output_files.append(
                self._export_image(
                    source_path=source_path,
                    output_path=output_path,
                    stem=record.path.stem,
                    export_format=export_format,
                )
            )
        return output_files

    @staticmethod
    def _export_image(
        *,
        source_path: Path,
        output_path: Path,
        stem: str,
        export_format: str,
    ) -> Path:
        if export_format not in SUPPORTED_EXPORT_FORMATS:
            raise ValueError(
                f"Unsupported export format {export_format!r}. "
                f"Supported formats: {', '.join(SUPPORTED_EXPORT_FORMATS)}."
            )

        destination_path = output_path / f"{stem}.{export_format}"
        source_resolved = source_path.resolve()
        destination_resolved = destination_path.resolve()
        if source_resolved == destination_resolved:
            return destination_path

        if source_path.suffix.lower() in {".jpg", ".jpeg"}:
            shutil.copy2(source_path, destination_path)
            return destination_path

        try:
            with Image.open(source_path) as image:
                image.convert("RGB").save(destination_path, format="JPEG", quality=95)
        except (UnidentifiedImageError, OSError) as exc:
            raise PipelineError(
                f"Unable to export {source_path} as JPEG. "
                "Use a supported input format or enable correction style processing."
            ) from exc

        return destination_path

    @staticmethod
    def _with_progress(
        iterable: Iterable[T],
        *,
        description: str,
        total: int | None,
        progress: ProgressCallback[T] | None,
    ) -> Iterable[T]:
        if progress is None:
            return iterable
        return progress(iterable, description, total)


def _normalise_style(style: str | None) -> str | None:
    if style is None:
        return None
    normalised = style.strip().lower()
    if not normalised:
        raise ValueError("--style cannot be empty.")
    if normalised == "none":
        return None
    return normalised


def _normalise_export_formats(export_formats: Iterable[str]) -> tuple[str, ...]:
    normalised = tuple(fmt.strip().lower() for fmt in export_formats if fmt.strip())
    if not normalised:
        raise ValueError("At least one export format must be selected.")
    unsupported = sorted(set(normalised) - set(SUPPORTED_EXPORT_FORMATS))
    if unsupported:
        raise ValueError(
            f"Unsupported export formats: {', '.join(unsupported)}. "
            f"Supported formats: {', '.join(SUPPORTED_EXPORT_FORMATS)}."
        )
    return normalised


def _default_threads() -> int:
    import os

    cpu_count = os.cpu_count() or 2
    return max(1, cpu_count // 2)
