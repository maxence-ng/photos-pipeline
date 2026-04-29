---
id: SPEC-013
title: "Intelligent Crop"
status: todo
phase: intermediate
epic: correction
priority: medium
effort: L
depends_on: ["SPEC-008"]
---

## User Story
As a photographer, I want the pipeline to automatically crop photos so that the main subject is well-composed (rule of thirds, centred face) rather than just centred by default.

## Acceptance Criteria
- [ ] `SmartCropper.crop(image: np.ndarray, target_ratio: float) -> CropRect` returns the best crop rectangle for the target aspect ratio
- [ ] **Portrait strategy**: detect faces → place largest face in upper-third intersection point
- [ ] **Non-portrait strategy**: detect salient region (OpenCV saliency or brightness-weighted centroid) → place in rule-of-thirds grid point
- [ ] Target ratios configurable: `1:1`, `4:3`, `3:2`, `16:9`, `original` (default: `original` = no crop)
- [ ] Minimum crop coverage: at least 70% of original area retained
- [ ] `--crop <ratio>` CLI flag; API `"crop": "16:9"` parameter
- [ ] Unit tests: portrait image → face is within upper-third zone of cropped result

## Technical Notes
- Face detection: reuse OpenCV DNN face detector (faster than Haar at this stage) — avoid adding a new dependency
- Saliency fallback: `cv2.saliency.StaticSaliencySpectralResidual_create()`
- Crop implementation: compute crop box mathematically, output as `(x, y, w, h)` tuple; actual crop applied via Darktable XMP or Pillow `.crop()`
- SmartCrop.js or Azure Vision are cloud alternatives (not used here to keep local-first)

## Implementation Hints
```python
@dataclass
class CropRect:
    x: int; y: int; w: int; h: int

class SmartCropper:
    def crop(self, image: np.ndarray, ratio: tuple[int, int] = None) -> CropRect:
        h, w = image.shape[:2]
        faces = self._detect_faces(image)
        if faces:
            return self._face_crop(w, h, faces[0], ratio)
        return self._saliency_crop(image, ratio)
```
