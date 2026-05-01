"""Unit tests for the Darktable CLI runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from photos_pipeline.config import get_settings
from photos_pipeline.modules.correction import (
    DARKTABLE_SUPPORTED_PARAMS,
    DarktableNotFoundError,
    DarktableProcessError,
    DarktableRunner,
    DarktableTimeoutError,
    DarktableVersionError,
)


def _completed_process(
    command: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


@pytest.mark.unit
def test_darktable_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTOS_PIPELINE_DARKTABLE_BINARY", "custom-darktable-cli")
    monkeypatch.setenv("PHOTOS_PIPELINE_DARKTABLE_BINARY_PATH", "C:\\tools\\darktable-cli.exe")
    monkeypatch.setenv("PHOTOS_PIPELINE_DARKTABLE_TIMEOUT_SECONDS", "75")
    monkeypatch.setenv("PHOTOS_PIPELINE_DARKTABLE_MIN_VERSION", "4.2")
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.darktable_binary == "custom-darktable-cli"
        assert settings.darktable_binary_path == Path("C:\\tools\\darktable-cli.exe")
        assert settings.darktable_timeout_seconds == 75
        assert settings.darktable_min_version == "4.2"
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_runner_resolves_binary_from_path(mocker, tmp_path: Path) -> None:
    binary_path = tmp_path / "darktable-cli"
    binary_path.write_text("", encoding="utf-8")
    mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        return_value=_completed_process(
            [str(binary_path), "--version"],
            stdout="this is darktable-cli 4.8.1",
        ),
    )

    runner = DarktableRunner(binary=binary_path)

    assert runner.binary == binary_path
    assert runner.version == "4.8.1"


@pytest.mark.unit
def test_runner_uses_windows_fallback_path(monkeypatch: pytest.MonkeyPatch, mocker, tmp_path: Path) -> None:
    fallback_binary = tmp_path / "darktable-cli.exe"
    fallback_binary.write_text("", encoding="utf-8")
    mocker.patch("photos_pipeline.modules.correction.darktable.shutil.which", return_value=None)
    mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        return_value=_completed_process(
            [str(fallback_binary), "--version"],
            stdout="darktable-cli 4.6.0",
        ),
    )
    monkeypatch.setattr("photos_pipeline.modules.correction.darktable.sys.platform", "win32")
    monkeypatch.setattr(
        "photos_pipeline.modules.correction.darktable._WINDOWS_DARKTABLE_PATHS",
        (fallback_binary,),
    )

    runner = DarktableRunner()

    assert runner.binary == fallback_binary


@pytest.mark.unit
def test_runner_raises_not_found_when_binary_missing(mocker) -> None:
    mocker.patch("photos_pipeline.modules.correction.darktable.shutil.which", return_value=None)
    mocker.patch(
        "photos_pipeline.modules.correction.darktable._WINDOWS_DARKTABLE_PATHS",
        (),
    )

    with pytest.raises(DarktableNotFoundError, match="darktable-cli could not be found"):
        DarktableRunner()


@pytest.mark.unit
def test_runner_raises_for_unsupported_version(mocker, tmp_path: Path) -> None:
    binary_path = tmp_path / "darktable-cli"
    binary_path.write_text("", encoding="utf-8")
    mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        return_value=_completed_process(
            [str(binary_path), "--version"],
            stdout="darktable-cli 3.8.1",
        ),
    )

    with pytest.raises(DarktableVersionError, match="4.0\\+ is required"):
        DarktableRunner(binary=binary_path)


@pytest.mark.unit
def test_supported_params_are_stable() -> None:
    assert DARKTABLE_SUPPORTED_PARAMS == ("xmp", "width", "height", "hq")


@pytest.mark.unit
def test_process_builds_expected_command(mocker, tmp_path: Path) -> None:
    binary_path = tmp_path / "darktable-cli"
    binary_path.write_text("", encoding="utf-8")
    input_path = tmp_path / "input.nef"
    output_path = tmp_path / "output.jpg"
    xmp_path = tmp_path / "correction.xmp"
    mock_run = mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        side_effect=[
            _completed_process([str(binary_path), "--version"], stdout="darktable-cli 4.8.1"),
            _completed_process([str(binary_path), str(input_path), str(output_path)]),
        ],
    )

    runner = DarktableRunner(binary=binary_path)
    result = runner.process(
        input_path,
        output_path,
        style="cinematic",
        params={
            "xmp": xmp_path,
            "width": 2000,
            "height": 1200,
            "hq": True,
        },
    )

    assert result == output_path
    assert mock_run.call_count == 2
    process_call = mock_run.call_args_list[1]
    assert process_call.kwargs["timeout"] == 60
    assert process_call.kwargs["capture_output"] is True
    assert process_call.kwargs["text"] is True
    assert process_call.kwargs["check"] is False
    assert process_call.args[0] == [
        str(binary_path),
        str(input_path),
        str(xmp_path),
        str(output_path),
        "--apply-custom-presets",
        "false",
        "--style",
        "cinematic",
        "--width",
        "2000",
        "--height",
        "1200",
        "--hq",
        "true",
    ]


@pytest.mark.unit
def test_process_rejects_unsupported_params(mocker, tmp_path: Path) -> None:
    binary_path = tmp_path / "darktable-cli"
    binary_path.write_text("", encoding="utf-8")
    mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        return_value=_completed_process(
            [str(binary_path), "--version"],
            stdout="darktable-cli 4.8.1",
        ),
    )
    runner = DarktableRunner(binary=binary_path)

    with pytest.raises(ValueError, match="Unsupported Darktable params"):
        runner.process(tmp_path / "input.nef", tmp_path / "output.jpg", params={"quality": 95})


@pytest.mark.unit
def test_process_raises_timeout(mocker, tmp_path: Path) -> None:
    binary_path = tmp_path / "darktable-cli"
    binary_path.write_text("", encoding="utf-8")
    mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        side_effect=[
            _completed_process([str(binary_path), "--version"], stdout="darktable-cli 4.8.1"),
            subprocess.TimeoutExpired(cmd=[str(binary_path)], timeout=60),
        ],
    )
    runner = DarktableRunner(binary=binary_path)

    with pytest.raises(DarktableTimeoutError, match="timed out after 60 seconds"):
        runner.process(tmp_path / "input.nef", tmp_path / "output.jpg")


@pytest.mark.unit
def test_process_raises_on_darktable_error(mocker, tmp_path: Path) -> None:
    binary_path = tmp_path / "darktable-cli"
    binary_path.write_text("", encoding="utf-8")
    mocker.patch(
        "photos_pipeline.modules.correction.darktable.subprocess.run",
        side_effect=[
            _completed_process([str(binary_path), "--version"], stdout="darktable-cli 4.8.1"),
            _completed_process(
                [str(binary_path), str(tmp_path / "input.nef"), str(tmp_path / "output.jpg")],
                returncode=1,
                stderr="error: unsupported image format",
            ),
        ],
    )
    runner = DarktableRunner(binary=binary_path)

    with pytest.raises(DarktableProcessError, match="unsupported image format"):
        runner.process(tmp_path / "input.nef", tmp_path / "output.jpg")
