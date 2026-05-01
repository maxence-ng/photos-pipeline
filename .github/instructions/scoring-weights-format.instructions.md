---
description: Keep default scorer weights compatible with the PyTorch NIMA loader.
applyTo: "src/photos_pipeline/config.py"
---

## Scorer weights format
- `DEFAULT_SCORER_WEIGHTS_URL` must resolve to a PyTorch-compatible `.pth` checkpoint that `load_nima_model()` can consume.
- Do not point the default URL at legacy Keras/HDF5 NIMA weights; the loader explicitly rejects HDF5 files with `ScorerWeightsLoadError`.
