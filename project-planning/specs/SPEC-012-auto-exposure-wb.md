---
id: SPEC-012
title: "Auto Exposure & White Balance Correction"
status: todo
phase: intermediate
epic: correction
priority: medium
effort: M
depends_on: ["SPEC-008"]
---

## User Story
As a user, I want the pipeline to automatically correct over/under-exposed photos and fix obvious white-balance issues so that I don't have to manually adjust every shot.

## Acceptance Criteria
- [ ] `ExposureCorrector.auto_correct(record: ImageRecord) -> dict` returns Darktable-compatible correction parameters
- [ ] Exposure correction: analyse image histogram; if median luminance is outside `[0.35, 0.65]` normalised range, compute an EV offset and apply it
- [ ] White balance correction: detect colour temperature using grey-world assumption or image metadata (`ColorTemp` EXIF tag); apply correction via Darktable or OpenCV
- [ ] Corrections are applied via Darktable XMP sidecar or directly in `darktable-cli` call (using `--icc-intent` and exposure params)
- [ ] Aggressiveness configurable: `--auto-correct none | mild | full` (default: `mild`)
- [ ] Under `mild`: only correct if deviation > 1 EV or WB off by > 500K
- [ ] Unit tests: dark image → positive EV applied; warm-cast image → cooler WB applied

## Technical Notes
- Darktable supports passing exposure correction via an XMP sidecar alongside the input RAW — this is the cleanest integration
- Alternative (Pillow-only): `ImageEnhance.Brightness`, `ImageEnhance.Color` — lower quality but no Darktable dependency
- Grey-world WB: `scale_r = mean(all_pixels) / mean(R_channel)` and similarly for B
- Document the limitation: auto correction is best-effort; photographers should review results in manual mode

## Implementation Hints
```python
def analyse_exposure(thumbnail: np.ndarray) -> float:
    """Returns EV offset needed to reach target median luminance."""
    grey = cv2.cvtColor(thumbnail, cv2.COLOR_BGR2GRAY)
    median = np.median(grey) / 255.0
    if 0.35 <= median <= 0.65:
        return 0.0
    target = 0.50
    return float(np.log2(target / median))   # EV shift
```
