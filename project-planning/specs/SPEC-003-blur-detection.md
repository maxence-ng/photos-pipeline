---
id: SPEC-003
title: "Blur Detection (Laplacian Variance)"
status: todo
phase: mvp
epic: culling
priority: high
effort: S
depends_on: ["SPEC-002"]
---

## User Story
As a user, I want blurry photos to be automatically detected and flagged so that I don't need to manually review out-of-focus or motion-blurred shots.

## Acceptance Criteria
- [ ] `BlurDetector.score(image: np.ndarray) -> float` returns the Laplacian variance of the image
- [ ] `BlurDetector.is_blurry(image, threshold) -> bool` returns `True` when score < threshold
- [ ] Default threshold configurable via `config.py` (default: `100.0`)
- [ ] Works on thumbnail images (avoids expensive full-RAW decode)
- [ ] Blurry images are tagged with `cull_reason: "blur"` and `blur_score: <float>` in `ImageRecord`
- [ ] Unit tests: one sharp fixture image (score > 200), one blurry fixture (score < 50)

## Technical Notes
- Convert image to greyscale before computing Laplacian: `cv2.Laplacian(grey, cv2.CV_64F).var()`
- Apply on centre crop (avoid black borders from RAW thumbnails) — crop central 80% by area
- The threshold is subjective; document in README that users should tune it for their equipment

## Implementation Hints
```python
import cv2

class BlurDetector:
    def __init__(self, threshold: float = 100.0):
        self.threshold = threshold

    def score(self, image: np.ndarray) -> float:
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(grey, cv2.CV_64F).var())

    def is_blurry(self, image: np.ndarray, threshold: float | None = None) -> bool:
        t = threshold if threshold is not None else self.threshold
        return self.score(image) < t
```
