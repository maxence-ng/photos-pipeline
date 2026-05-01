"""Unit tests for style preset management."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from photos_pipeline.modules.correction import (
    BUILTIN_PRESET_NAMES,
    PresetFallbackNotSupportedError,
    PresetManager,
    PresetNotFoundError,
)
from photos_pipeline.modules.correction.darktable import DarktableNotFoundError
from photos_pipeline.modules.ingestion import ImageRecord


def _make_jpeg(path: Path) -> ImageRecord:
    Image.new("RGB", (16, 16), color=(200, 100, 50)).save(path, format="JPEG")
    return ImageRecord(path=path, format="jpeg")


@pytest.mark.unit
def test_list_presets_returns_builtin_presets() -> None:
    manager = PresetManager(custom_styles_dir=Path("C:\\definitely-missing-style-dir"))

    presets = manager.list_presets()

    assert [preset.name for preset in presets] == list(BUILTIN_PRESET_NAMES)
    assert all(preset.source == "builtin" for preset in presets)
    assert all(preset.path.is_file() for preset in presets)


@pytest.mark.unit
def test_list_presets_includes_custom_presets(tmp_path: Path) -> None:
    custom_styles = tmp_path / "styles"
    custom_styles.mkdir()
    (custom_styles / "travel-look.dtstyle").write_text("<style />", encoding="utf-8")
    (custom_styles / "natural.dtstyle").write_text("<style />", encoding="utf-8")

    manager = PresetManager(custom_styles_dir=custom_styles)
    presets_by_name = {preset.name: preset for preset in manager.list_presets()}

    assert "travel-look" in presets_by_name
    assert presets_by_name["travel-look"].source == "custom"
    assert presets_by_name["natural"].source == "custom"


@pytest.mark.unit
def test_apply_delegates_to_darktable_runner(tmp_path: Path, mocker) -> None:
    record = _make_jpeg(tmp_path / "input.jpg")
    expected_output = tmp_path / "input.styled.jpg"
    runner = mocker.Mock()
    runner.process.return_value = expected_output
    manager = PresetManager(darktable_runner=runner, custom_styles_dir=tmp_path / "styles")

    result = manager.apply(record, "cinematic")

    assert result == expected_output
    runner.process.assert_called_once_with(record.path, expected_output, style="cinematic")


@pytest.mark.unit
def test_apply_unknown_preset_raises_not_found(tmp_path: Path) -> None:
    record = _make_jpeg(tmp_path / "input.jpg")
    manager = PresetManager(custom_styles_dir=tmp_path / "styles")

    with pytest.raises(PresetNotFoundError, match="Available presets"):
        manager.apply(record, "unknown-style")


@pytest.mark.unit
def test_apply_none_skips_processing(tmp_path: Path, mocker) -> None:
    record = _make_jpeg(tmp_path / "input.jpg")
    runner = mocker.Mock()
    manager = PresetManager(darktable_runner=runner, custom_styles_dir=tmp_path / "styles")

    result = manager.apply(record, "none")

    assert result == record.path
    runner.process.assert_not_called()


class _MissingDarktableRunner:
    def process(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        raise DarktableNotFoundError("darktable-cli missing")


@pytest.mark.unit
def test_apply_uses_software_fallback_when_darktable_missing(tmp_path: Path) -> None:
    record = _make_jpeg(tmp_path / "input.jpg")
    manager = PresetManager(
        darktable_runner=_MissingDarktableRunner(),
        custom_styles_dir=tmp_path / "styles",
    )

    output = manager.apply(record, "bw-classic")

    assert output.exists()
    with Image.open(output) as image:
        r, g, b = image.split()
    assert r.tobytes() == g.tobytes() == b.tobytes()


@pytest.mark.unit
def test_apply_fallback_rejects_unsupported_preset(tmp_path: Path) -> None:
    record = _make_jpeg(tmp_path / "input.jpg")
    manager = PresetManager(
        darktable_runner=_MissingDarktableRunner(),
        custom_styles_dir=tmp_path / "styles",
    )

    with pytest.raises(PresetFallbackNotSupportedError, match="Supported fallback presets"):
        manager.apply(record, "natural")
