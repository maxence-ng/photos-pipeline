---
id: SPEC-008
title: "Darktable CLI Integration"
status: in-progress
phase: mvp
epic: correction
priority: high
effort: M
depends_on: ["SPEC-002"]
---

## User Story
As a user, I want RAW files developed and exported with professional-grade processing (Darktable) so that the output quality matches what a photographer would produce manually.

## Acceptance Criteria
- [x] `DarktableRunner.process(input: Path, output: Path, style: str | None, params: dict) -> Path` calls `darktable-cli` and returns the output path
- [ ] Supports all RAW formats from SPEC-002 (ORF, CR2, NEF, RAF, ARW, RW2) as well as JPEG
- [x] `--style` parameter passes a named Darktable style if specified
- [x] `--apply-custom-presets false` is set by default to avoid applying user's local presets unexpectedly
- [x] Timeout configurable (default: 60 s per image); process is killed and error logged on timeout
- [x] If `darktable-cli` is not found on PATH, raise `DarktableNotFoundError` with install instructions
- [x] Darktable version ≥ 4.0 required; version is checked at startup
- [x] Unit tests: mock subprocess, verify correct CLI flags are assembled

## Technical Notes
- Darktable CLI invocation pattern:
  ```
  darktable-cli <input> [<xmp>] <output> [--style <name>] [--width W] [--height H] [--hq true]
  ```
- Run via `subprocess.run()` with `capture_output=True`, `timeout=timeout_s`
- Darktable writes to stdout/stderr; parse stderr for error signals
- On Windows, Darktable must be installed; its binary may be at `C:\Program Files\darktable\bin\darktable-cli.exe` — search common locations and PATH

## Implementation Hints
```python
import shutil, subprocess
from pathlib import Path

class DarktableRunner:
    def __init__(self, binary: str = "darktable-cli", timeout: int = 60):
        self.binary = shutil.which(binary) or self._find_binary()
        self.timeout = timeout

    def process(self, input: Path, output: Path, style: str | None = None) -> Path:
        cmd = [self.binary, str(input), str(output), "--apply-custom-presets", "false"]
        if style:
            cmd += ["--style", style]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if result.returncode != 0:
            raise DarktableError(result.stderr)
        return output
```
