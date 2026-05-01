---
id: SPEC-009
title: "Style Presets Management"
status: in-progress
phase: mvp
epic: correction
priority: high
effort: M
depends_on: ["SPEC-008"]
---

## User Story
As a user, I want to select a visual style (e.g. Natural, Cinematic, B&W) at the start of a session so that all exported photos share a consistent look without manual adjustment.

## Acceptance Criteria
- [x] `PresetManager.list_presets() -> list[Preset]` returns all available presets
- [x] Built-in presets: `natural`, `cinematic`, `portrait-warm`, `landscape`, `bw-classic`, `bw-high-contrast`
- [x] Each preset maps to a Darktable `.dtstyle` file stored in `src/photos_pipeline/assets/styles/`
- [x] Users can add custom presets by dropping `.dtstyle` files into `~/.photos_pipeline/styles/` — these appear alongside built-in ones
- [x] `PresetManager.apply(record: ImageRecord, preset_name: str) -> Path` delegates to `DarktableRunner` with the correct `--style` argument
- [x] If a requested preset name doesn't exist, raise `PresetNotFoundError` listing available options
- [x] CLI flag `--style <name>` selects the preset; `--style none` skips style application
- [ ] API accepts `"style": "<name>"` in the job start payload

## Technical Notes
- Darktable style files are XML-based; ship minimal but visually distinct built-in styles
- Since creating actual Darktable `.dtstyle` files requires Darktable itself, **stub files** are acceptable for initial implementation with a note in README on how to export styles from Darktable GUI
- Fallback for environments without Darktable: implement a "software preset" mode using Pillow/OpenCV (e.g. desaturate for B&W, curve adjustments for cinematic) — quality will be lower but usable
- Current implementation scope: minimal software fallback for `cinematic`, `bw-classic`, and `bw-high-contrast` on JPEG inputs

## Implementation Hints
```
src/photos_pipeline/assets/styles/
  natural.dtstyle
  cinematic.dtstyle
  portrait-warm.dtstyle
  landscape.dtstyle
  bw-classic.dtstyle
  bw-high-contrast.dtstyle
```
