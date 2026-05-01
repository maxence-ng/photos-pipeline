---
description: Preserve the shared NIMA inference contract in the scoring module.
applyTo: "src/photos_pipeline/modules/scoring/**"
---

## NIMA inference contract
- Keep the scorer API centered on RGB `np.ndarray` inputs with shape `(H, W, 3)`.
- Reuse the shared ImageNet preprocessing path for NIMA inference: `Resize(256)`, `CenterCrop(224)`, then normalise with `IMAGENET_MEAN` and `IMAGENET_STD`.
- Preserve batched inference; `score()` should stay a thin wrapper over `score_batch()`.
- Convert 10-way model outputs into the final `1..10` aesthetic score via expected-value computation, only applying softmax when the outputs are not already probabilities.
