---
id: SPEC-011
title: "JPEG Export (basic)"
status: todo
phase: mvp
epic: export
priority: high
effort: S
depends_on: ["SPEC-008"]
---

## User Story
As a user, I want processed images exported as JPEG files with configurable quality so that I get web-ready and client-ready outputs without further action.

## Acceptance Criteria
- [ ] `Exporter.export_jpeg(record: ImageRecord, output_dir: Path, quality: int) -> Path` produces a JPEG at the given quality
- [ ] Quality range: 1–100 (default: `85` for web, `95` for client)
- [ ] Output filename convention: `<original_stem>_<style>.jpg` (e.g. `IMG_001_natural.jpg`)
- [ ] Output directory created automatically if it doesn't exist
- [ ] EXIF metadata copied from source to output (using ExifTool or Pillow)
- [ ] If Darktable was used for processing, the output comes directly from `DarktableRunner`; otherwise Pillow writes the JPEG
- [ ] Unit tests: output file exists, is valid JPEG, file size within expected range

## Technical Notes
- Darktable outputs a JPEG directly when given a `.jpg` output path — leverage this
- For JPEG-to-JPEG (no RAW), Pillow can handle the quality re-encode
- EXIF copy: use `piexif` library to copy EXIF block from source to re-encoded JPEG (`piexif.transplant()`)
- Warn if quality < 70 (potential visible artefacts)

## Implementation Hints
```python
from PIL import Image
import piexif

def export_jpeg(source: Path, output: Path, quality: int = 85) -> Path:
    img = Image.open(source)
    exif_bytes = piexif.dump(piexif.load(source.as_posix()))
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="JPEG", quality=quality, exif=exif_bytes)
    return output
```
