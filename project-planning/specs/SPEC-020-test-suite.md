---
id: SPEC-020
title: "Full Test Suite"
status: todo
phase: advanced
epic: testing-docs
priority: high
effort: L
depends_on: ["SPEC-010", "SPEC-014"]
---

## User Story
As a developer, I want a comprehensive test suite covering unit, integration, and performance tests so that regressions are caught automatically on every commit.

## Acceptance Criteria
- [ ] **Unit tests** for every module: blur detection, duplicate detection, closed-eye, burst selection, NIMA scorer, Darktable runner (mocked), exporter, metadata handler, CLI commands, API endpoints
- [ ] **Integration test**: end-to-end pipeline run on a fixture dataset (≥ 10 images including ORF, JPEG, blurry pair, duplicate pair, portrait with closed eyes)
- [ ] **Coverage** ≥ 80% (enforced in CI via `pytest-cov --fail-under=80`)
- [ ] **Performance test**: batch of 50 JPEG thumbnails processed in < 30 s on a 4-core machine (no GPU)
- [ ] Fixture images stored in `tests/fixtures/` (small resolution, cleared for use, no PII)
- [ ] `pytest` configuration in `pyproject.toml`; markers: `unit`, `integration`, `slow`
- [ ] CI skips `slow` tests on PRs; runs full suite on main branch merges

## Technical Notes
- Use `pytest-mock` and `unittest.mock` for mocking subprocess calls (Darktable, ExifTool)
- Fixture images: create synthetic test images programmatically with Pillow (blur via Gaussian filter, duplicate via copy, closed-eye via drawing) — avoids copyright/PII issues
- `Faker` can generate synthetic EXIF data for metadata tests
- Performance test: `pytest-benchmark` or simple `time.perf_counter` assertions

## Fixture Generation Script
```python
# tests/generate_fixtures.py
from PIL import Image, ImageFilter
import numpy as np

def make_blurry(path):
    img = Image.fromarray(np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8))
    img.filter(ImageFilter.GaussianBlur(radius=10)).save(path)

def make_sharp(path):
    img = Image.fromarray(np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8))
    img.save(path)
```
