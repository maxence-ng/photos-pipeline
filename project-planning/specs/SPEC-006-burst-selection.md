---
id: SPEC-006
title: "Burst Shot Selection"
status: todo
phase: mvp
epic: culling
priority: medium
effort: M
depends_on: ["SPEC-003"]
---

## User Story
As a photographer, I want the pipeline to automatically identify burst sequences and select the sharpest/best-scored frame from each burst so that my output set isn't flooded with near-identical consecutive shots.

## Acceptance Criteria
- [ ] `BurstGrouper.group(records: list[ImageRecord]) -> list[BurstGroup]` groups images taken within `burst_gap_seconds` (default: `2.0`) of each other by the same camera
- [ ] `BurstSelector.select_best(group: BurstGroup) -> ImageRecord` returns the image with the highest composite score
- [ ] Composite score = `0.6 * normalised_blur_score + 0.4 * normalised_aesthetic_score` (weights configurable)
- [ ] Non-selected burst frames are tagged `cull_reason: "burst_duplicate"` and `burst_group_id: <uuid>`
- [ ] If `aesthetic_score` is not yet computed (scoring module not run), selection falls back to blur score only
- [ ] Single images (not part of a burst) pass through unchanged
- [ ] Unit tests: sequence of 5 images with one clearly sharp → correct one selected

## Technical Notes
- Grouping: sort by `capture_datetime`, then apply a sliding window; same camera model is required (different cameras shooting simultaneously should not be merged)
- If `capture_datetime` is `None`, fall back to file modification time
- Use a UUID per burst group for traceability in the output report

## Implementation Hints
```python
@dataclass
class BurstGroup:
    group_id: str          # UUID
    images: list[ImageRecord]
    best: ImageRecord | None = None

def group_by_time(records: list[ImageRecord], gap_s: float = 2.0) -> list[BurstGroup]:
    sorted_records = sorted(records, key=lambda r: r.capture_datetime or datetime.min)
    # sliding window grouping...
```
