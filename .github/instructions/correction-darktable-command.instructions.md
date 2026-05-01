---
description: Preserve the Darktable CLI command contract.
applyTo: "src/photos_pipeline/modules/correction/darktable.py"
---

## Darktable process command contract
- Keep `DarktableRunner.process()` limited to the allowlisted `params` keys: `xmp`, `width`, `height`, and `hq`.
- Preserve the positional CLI shape `darktable-cli <input> [<xmp>] <output>`.
- Always append `--apply-custom-presets false` so local Darktable presets are never applied implicitly.
- Keep optional flags deterministic: `--style` first when present, then `--width`, `--height`, and `--hq` in that order.
- Coerce `width`/`height` as positive integers and `hq` as `true`/`false`; reject unsupported or malformed params with `ValueError`.
