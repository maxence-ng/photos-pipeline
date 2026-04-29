---
id: SPEC-005
title: "Closed-Eye Detection"
status: todo
phase: mvp
epic: culling
priority: medium
effort: M
depends_on: ["SPEC-002"]
---

## User Story
As a photographer shooting portraits, I want photos where subjects have closed eyes to be automatically flagged so that I don't accidentally deliver them to clients.

## Acceptance Criteria
- [ ] `ClosedEyeDetector.detect(image) -> list[FaceResult]` detects all faces and, per face, determines if eyes are open or closed
- [ ] Images where **any** detected face has closed eyes are tagged `cull_reason: "closed_eyes"`
- [ ] Configurable sensitivity: `eye_ar_threshold` (Eye Aspect Ratio, default `0.20`)
- [ ] If no face is detected in an image, the image is **not** flagged (pass-through)
- [ ] Works on thumbnail resolution (max 800px)
- [ ] Unit tests: portrait with eyes open (not flagged), portrait with eyes closed (flagged), landscape photo (not flagged)

## Technical Notes
- **Primary method:** OpenCV `dlib` landmarks (68-point model) — compute Eye Aspect Ratio (EAR) from 6 landmark points per eye
- **Fallback:** OpenCV Haar Cascade for face detection + heuristic eye region if dlib unavailable
- EAR formula: `EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)` — EAR < threshold → eye closed
- Dlib model file (`shape_predictor_68_face_landmarks.dat`) must be downloaded separately; document in README; store in `~/.photos_pipeline/models/`
- Consider mediapipe as alternative (no separate model download needed)

## Implementation Hints
```python
# Using mediapipe FaceMesh (simpler dependency)
import mediapipe as mp

class ClosedEyeDetector:
    LEFT_EYE_INDICES  = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]

    def __init__(self, ear_threshold: float = 0.20):
        self.threshold = ear_threshold
        self.mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True)
```
