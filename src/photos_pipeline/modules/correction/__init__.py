"""Correction module package."""

from photos_pipeline.modules.correction.darktable import (
    DARKTABLE_SUPPORTED_EXTENSIONS,
    DARKTABLE_SUPPORTED_PARAMS,
    DarktableError,
    DarktableNotFoundError,
    DarktableProcessError,
    DarktableRunner,
    DarktableTimeoutError,
    DarktableUnsupportedFormatError,
    DarktableVersionError,
    supports_darktable_input,
)
from photos_pipeline.modules.correction.presets import (
    BUILTIN_PRESET_NAMES,
    DEFAULT_CUSTOM_STYLES_DIR,
    SOFTWARE_FALLBACK_PRESET_NAMES,
    Preset,
    PresetError,
    PresetFallbackNotSupportedError,
    PresetManager,
    PresetNotFoundError,
)

__all__ = [
    "BUILTIN_PRESET_NAMES",
    "DARKTABLE_SUPPORTED_EXTENSIONS",
    "DARKTABLE_SUPPORTED_PARAMS",
    "DEFAULT_CUSTOM_STYLES_DIR",
    "DarktableError",
    "DarktableNotFoundError",
    "DarktableProcessError",
    "DarktableRunner",
    "DarktableTimeoutError",
    "DarktableUnsupportedFormatError",
    "DarktableVersionError",
    "Preset",
    "PresetError",
    "PresetFallbackNotSupportedError",
    "PresetManager",
    "PresetNotFoundError",
    "SOFTWARE_FALLBACK_PRESET_NAMES",
    "supports_darktable_input",
]
