---
description: Keep Darktable availability checks fail-fast.
applyTo: "src/photos_pipeline/modules/correction/darktable.py"
---

## Darktable runner initialization
- `DarktableRunner` should resolve the executable and validate `darktable-cli --version` during `__init__`, not lazily on first `process()` call.
- Construction must fail with `DarktableNotFoundError` or `DarktableVersionError` when discovery or version checks fail.
- Preserve the discovery order: explicit `binary` argument, configured `darktable_binary_path`, PATH lookup via `darktable_binary`, then Windows fallback install locations.
- This module is the current correction startup gate, so fail-fast initialization is part of its public contract until a broader lifecycle replaces it.
