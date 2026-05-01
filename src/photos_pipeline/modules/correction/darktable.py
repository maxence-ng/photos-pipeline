"""Darktable CLI integration for the correction stage."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from photos_pipeline.config import Settings, get_settings
from photos_pipeline.modules.ingestion import SUPPORTED_EXTENSIONS

__all__ = [
    "DARKTABLE_SUPPORTED_PARAMS",
    "DARKTABLE_SUPPORTED_EXTENSIONS",
    "DarktableError",
    "DarktableNotFoundError",
    "DarktableProcessError",
    "DarktableRunner",
    "DarktableTimeoutError",
    "DarktableUnsupportedFormatError",
    "DarktableVersionError",
    "supports_darktable_input",
]

logger = logging.getLogger(__name__)

DARKTABLE_SUPPORTED_PARAMS: tuple[str, ...] = ("xmp", "width", "height", "hq")
DARKTABLE_SUPPORTED_EXTENSIONS: frozenset[str] = SUPPORTED_EXTENSIONS

_VERSION_PATTERN = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?")
_WINDOWS_DARKTABLE_PATHS: tuple[Path, ...] = (
    Path(r"C:\Program Files\darktable\bin\darktable-cli.exe"),
    Path(r"C:\Program Files (x86)\darktable\bin\darktable-cli.exe"),
)
_OPTION_FLAG_ORDER: tuple[tuple[str, str], ...] = (
    ("width", "--width"),
    ("height", "--height"),
    ("hq", "--hq"),
)


class DarktableError(RuntimeError):
    """Base class for Darktable integration failures."""


class DarktableNotFoundError(DarktableError):
    """Raised when darktable-cli cannot be located."""


class DarktableVersionError(DarktableError):
    """Raised when the installed Darktable version is unsupported."""


class DarktableProcessError(DarktableError):
    """Raised when darktable-cli exits with a non-zero status."""


class DarktableTimeoutError(DarktableError):
    """Raised when a darktable-cli invocation exceeds the configured timeout."""


class DarktableUnsupportedFormatError(DarktableError):
    """Raised when a file extension is unsupported by the Darktable runner."""


def _parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.search(value)
    if match is None:
        raise DarktableVersionError(f"Could not parse a Darktable version from output: {value!r}")

    patch = match.group("patch") or "0"
    return (int(match.group("major")), int(match.group("minor")), int(patch))


def _format_version(value: tuple[int, int, int]) -> str:
    major, minor, patch = value
    return f"{major}.{minor}.{patch}"


def _not_found_message(binary_name: str) -> str:
    return (
        f"darktable-cli could not be found using {binary_name!r}. "
        "Install Darktable 4.0+ and ensure darktable-cli is on PATH, or set "
        "PHOTOS_PIPELINE_DARKTABLE_BINARY_PATH to the executable location."
    )


def supports_darktable_input(path: Path) -> bool:
    """Return ``True`` when *path* uses a supported RAW/JPEG extension."""
    return path.suffix.lower() in DARKTABLE_SUPPORTED_EXTENSIONS


class DarktableRunner:
    """Resolve, validate, and invoke ``darktable-cli``."""

    def __init__(
        self,
        *,
        binary: str | Path | None = None,
        timeout: int | None = None,
        min_version: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()

        self.timeout = timeout or resolved_settings.darktable_timeout_seconds
        self.min_version = min_version or resolved_settings.darktable_min_version
        self.binary = self._resolve_binary(
            binary=binary,
            configured_path=resolved_settings.darktable_binary_path,
            configured_name=resolved_settings.darktable_binary,
        )
        self.version = self._validate_version()

    def process(
        self,
        input: Path,
        output: Path,
        style: str | None = None,
        params: Mapping[str, object] | None = None,
    ) -> Path:
        """Process *input* into *output* via ``darktable-cli``."""
        self._validate_input_path(input)
        command = self._build_process_command(input=input, output=output, style=style, params=params)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("darktable-cli timed out for %s after %s seconds", input, self.timeout)
            raise DarktableTimeoutError(
                f"darktable-cli timed out after {self.timeout} seconds while processing {input}."
            ) from exc
        except OSError as exc:
            raise DarktableProcessError(
                f"Failed to execute darktable-cli for {input}: {exc}"
            ) from exc

        if result.returncode != 0:
            error_output = result.stderr.strip() or result.stdout.strip()
            message = error_output or f"darktable-cli exited with code {result.returncode}."
            logger.error("darktable-cli failed for %s: %s", input, message)
            raise DarktableProcessError(
                f"darktable-cli failed for {input}: {message}"
            )

        return output

    @staticmethod
    def _validate_input_path(input_path: Path) -> None:
        if supports_darktable_input(input_path):
            return

        supported_extensions = ", ".join(sorted(DARKTABLE_SUPPORTED_EXTENSIONS))
        raise DarktableUnsupportedFormatError(
            "Unsupported input format for Darktable: "
            f"{input_path.suffix or '<no extension>'}. Supported extensions are: {supported_extensions}."
        )

    @classmethod
    def _resolve_binary(
        cls,
        *,
        binary: str | Path | None,
        configured_path: Path | None,
        configured_name: str,
    ) -> Path:
        explicit_candidate = str(binary) if binary is not None else None
        if explicit_candidate is not None:
            return cls._resolve_explicit_candidate(explicit_candidate)

        if configured_path is not None:
            if configured_path.is_file():
                return configured_path
            raise DarktableNotFoundError(_not_found_message(str(configured_path)))

        discovered = shutil.which(configured_name)
        if discovered is not None:
            return Path(discovered)

        if sys.platform.startswith("win"):
            for candidate in _WINDOWS_DARKTABLE_PATHS:
                if candidate.is_file():
                    return candidate

        raise DarktableNotFoundError(_not_found_message(configured_name))

    @staticmethod
    def _resolve_explicit_candidate(candidate: str) -> Path:
        explicit_path = Path(candidate)
        if explicit_path.is_file():
            return explicit_path

        discovered = shutil.which(candidate)
        if discovered is not None:
            return Path(discovered)

        raise DarktableNotFoundError(_not_found_message(candidate))

    def _validate_version(self) -> str:
        command = [str(self.binary), "--version"]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DarktableVersionError(
                f"Timed out after {self.timeout} seconds while checking Darktable version."
            ) from exc
        except OSError as exc:
            raise DarktableNotFoundError(_not_found_message(str(self.binary))) from exc

        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            if not message:
                message = f"darktable-cli exited with code {result.returncode} while reporting its version."
            raise DarktableVersionError(f"Could not determine Darktable version: {message}")

        output = result.stdout.strip() or result.stderr.strip()
        detected = _parse_version(output)
        minimum = _parse_version(self.min_version)
        if detected < minimum:
            raise DarktableVersionError(
                "Darktable version "
                f"{_format_version(detected)} is installed, but version "
                f"{self.min_version}+ is required."
            )

        return _format_version(detected)

    def _build_process_command(
        self,
        *,
        input: Path,
        output: Path,
        style: str | None,
        params: Mapping[str, object] | None,
    ) -> list[str]:
        normalised_params = params or {}
        unsupported = sorted(set(normalised_params) - set(DARKTABLE_SUPPORTED_PARAMS))
        if unsupported:
            unsupported_list = ", ".join(unsupported)
            raise ValueError(
                f"Unsupported Darktable params: {unsupported_list}. "
                f"Supported params are: {', '.join(DARKTABLE_SUPPORTED_PARAMS)}."
            )

        command = [str(self.binary), str(input)]

        xmp_value = normalised_params.get("xmp")
        if xmp_value is not None:
            command.append(self._coerce_path_like(xmp_value, key="xmp"))

        command.extend([str(output), "--apply-custom-presets", "false"])

        if style:
            command.extend(["--style", style])

        for key, flag in _OPTION_FLAG_ORDER:
            value = normalised_params.get(key)
            if value is None:
                continue

            if key in {"width", "height"}:
                command.extend([flag, self._coerce_positive_int(value, key=key)])
                continue

            if key == "hq":
                command.extend([flag, self._coerce_bool(value, key=key)])

        return command

    @staticmethod
    def _coerce_path_like(value: object, *, key: str) -> str:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, str) and value:
            return value
        raise ValueError(f"Darktable param {key!r} must be a non-empty path string or Path.")

    @staticmethod
    def _coerce_positive_int(value: object, *, key: str) -> str:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"Darktable param {key!r} must be a positive integer.")
        return str(value)

    @staticmethod
    def _coerce_bool(value: object, *, key: str) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower()
        raise ValueError(f"Darktable param {key!r} must be a boolean or 'true'/'false' string.")
