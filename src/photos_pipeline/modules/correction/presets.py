"""Style preset management for the correction stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance

from photos_pipeline.modules.correction.darktable import DarktableNotFoundError, DarktableRunner
from photos_pipeline.modules.ingestion import ImageRecord

BUILTIN_PRESET_NAMES: tuple[str, ...] = (
    "natural",
    "cinematic",
    "portrait-warm",
    "landscape",
    "bw-classic",
    "bw-high-contrast",
)
SOFTWARE_FALLBACK_PRESET_NAMES: frozenset[str] = frozenset(
    {"cinematic", "bw-classic", "bw-high-contrast"}
)
DEFAULT_CUSTOM_STYLES_DIR = Path.home() / ".photos_pipeline" / "styles"

__all__ = [
    "BUILTIN_PRESET_NAMES",
    "DEFAULT_CUSTOM_STYLES_DIR",
    "SOFTWARE_FALLBACK_PRESET_NAMES",
    "Preset",
    "PresetError",
    "PresetFallbackNotSupportedError",
    "PresetManager",
    "PresetNotFoundError",
]


class PresetError(RuntimeError):
    """Base class for style preset management errors."""


class PresetNotFoundError(PresetError):
    """Raised when a requested style preset does not exist."""


class PresetFallbackNotSupportedError(PresetError):
    """Raised when software fallback cannot handle a requested preset."""


@dataclass(slots=True, frozen=True)
class Preset:
    """A style preset resolved from bundled assets or custom user files."""

    name: str
    path: Path
    source: Literal["builtin", "custom"]


class PresetManager:
    """Discover and apply named style presets."""

    def __init__(
        self,
        *,
        darktable_runner: DarktableRunner | None = None,
        custom_styles_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.darktable_runner = darktable_runner
        self.custom_styles_dir = custom_styles_dir or DEFAULT_CUSTOM_STYLES_DIR
        self.output_dir = output_dir

    def list_presets(self) -> list[Preset]:
        """Return available built-in and custom presets."""
        presets = self._load_builtin_presets()
        presets.update(self._load_custom_presets())

        ordered_names: list[str] = []
        for name in BUILTIN_PRESET_NAMES:
            if name in presets:
                ordered_names.append(name)

        ordered_names.extend(
            sorted(name for name, preset in presets.items() if preset.source == "custom" and name not in ordered_names)
        )
        return [presets[name] for name in ordered_names]

    def apply(self, record: ImageRecord, preset_name: str) -> Path:
        """Apply *preset_name* to *record* and return the generated file path."""
        normalised_name = _normalise_preset_name(preset_name)
        if normalised_name == "none":
            return record.path

        available_presets = {preset.name: preset for preset in self.list_presets()}
        preset = available_presets.get(normalised_name)
        if preset is None:
            available_options = ", ".join(["none", *sorted(available_presets)])
            raise PresetNotFoundError(
                f"Preset {preset_name!r} was not found. Available presets: {available_options}."
            )

        output_path = self._output_path_for(record.path)
        runner = self.darktable_runner or DarktableRunner()
        try:
            return runner.process(record.path, output_path, style=preset.name)
        except DarktableNotFoundError as exc:
            return self._apply_software_fallback(record=record, preset_name=preset.name, output_path=output_path, error=exc)

    @staticmethod
    def _builtin_styles_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "styles"

    def _load_builtin_presets(self) -> dict[str, Preset]:
        styles_dir = self._builtin_styles_dir()
        presets: dict[str, Preset] = {}
        for name in BUILTIN_PRESET_NAMES:
            style_path = styles_dir / f"{name}.dtstyle"
            if not style_path.is_file():
                raise PresetError(f"Built-in style file is missing: {style_path}")
            presets[name] = Preset(name=name, path=style_path, source="builtin")
        return presets

    def _load_custom_presets(self) -> dict[str, Preset]:
        presets: dict[str, Preset] = {}
        if not self.custom_styles_dir.is_dir():
            return presets

        for style_path in sorted(self.custom_styles_dir.glob("*.dtstyle")):
            normalised_name = _normalise_preset_name(style_path.stem)
            if not normalised_name:
                continue
            presets[normalised_name] = Preset(name=normalised_name, path=style_path, source="custom")
        return presets

    def _output_path_for(self, input_path: Path) -> Path:
        target_dir = self.output_dir or input_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{input_path.stem}.styled.jpg"

    def _apply_software_fallback(
        self,
        *,
        record: ImageRecord,
        preset_name: str,
        output_path: Path,
        error: DarktableNotFoundError,
    ) -> Path:
        if preset_name not in SOFTWARE_FALLBACK_PRESET_NAMES:
            fallback_names = ", ".join(sorted(SOFTWARE_FALLBACK_PRESET_NAMES))
            raise PresetFallbackNotSupportedError(
                f"Darktable is unavailable and preset {preset_name!r} does not support software fallback. "
                f"Supported fallback presets: {fallback_names}."
            ) from error

        if record.format != "jpeg":
            raise PresetFallbackNotSupportedError(
                "Software preset fallback currently supports JPEG inputs only."
            ) from error

        with Image.open(record.path) as image:
            result = self._apply_software_style(image.convert("RGB"), preset_name)
        result.save(output_path, format="JPEG", quality=95)
        return output_path

    @staticmethod
    def _apply_software_style(image: Image.Image, preset_name: str) -> Image.Image:
        if preset_name == "bw-classic":
            return image.convert("L").convert("RGB")
        if preset_name == "bw-high-contrast":
            bw_image = image.convert("L")
            return ImageEnhance.Contrast(bw_image).enhance(1.6).convert("RGB")
        if preset_name == "cinematic":
            styled = ImageEnhance.Color(image).enhance(0.85)
            styled = ImageEnhance.Contrast(styled).enhance(1.2)
            return ImageEnhance.Brightness(styled).enhance(0.95)
        raise PresetFallbackNotSupportedError(f"Software fallback preset is not supported: {preset_name!r}.")


def _normalise_preset_name(value: str) -> str:
    return value.strip().lower()
