---
id: SPEC-004
title: "Duplicate Detection (pHash)"
status: done
phase: mvp
epic: culling
priority: high
effort: S
depends_on: ["SPEC-002"]
---

## User Story
As a user, I want near-identical duplicate photos detected and grouped so that only the best representative image from each duplicate cluster is kept.

## Acceptance Criteria
- [x] `DuplicateDetector` computes a perceptual hash (pHash) for each image thumbnail
- [x] Images with a Hamming distance ≤ `threshold` (default: `10`) are grouped as duplicates
- [x] Returns a `list[DuplicateGroup]` where each group contains the images and a nominated `best` image (sharpest by blur score)
- [x] Non-nominated duplicates are tagged `cull_reason: "duplicate"` in `ImageRecord`
- [x] Configurable hash algorithm: `phash` (default), `dhash`, `ahash` via config
- [x] Unit tests: two near-identical JPEG fixtures → grouped; two different images → not grouped

## Technical Notes
- Use `imagehash` library (`pip install imagehash`)
- pHash is robust to minor exposure/crop/resize differences
- For large batches, compute all hashes first, then O(n²) comparison is acceptable up to ~2000 images; above that, use `imagededup` with its built-in indexing
- When selecting the best from a group, use blur score from SPEC-003; fall back to capture datetime (prefer latest) if scores are equal

## Implementation Hints
```python
import imagehash
from PIL import Image

def compute_phash(thumbnail: np.ndarray) -> imagehash.ImageHash:
    pil = Image.fromarray(cv2.cvtColor(thumbnail, cv2.COLOR_BGR2RGB))
    return imagehash.phash(pil)

def hamming(h1, h2) -> int:
    return h1 - h2   # imagehash overloads subtraction to return Hamming distance
```
