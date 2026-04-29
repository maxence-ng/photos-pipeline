---
id: SPEC-014
title: "Multi-Format Export (PNG / TIFF / PDF)"
status: todo
phase: intermediate
epic: export
priority: medium
effort: M
depends_on: ["SPEC-011"]
---

## User Story
As a professional photographer, I want to export images in multiple formats simultaneously (JPEG for web, TIFF for archival, PDF for photo books) so that each deliverable channel receives the appropriate file.

## Acceptance Criteria
- [ ] `Exporter.export(record, output_dir, formats: list[str], options: ExportOptions) -> dict[str, Path]`
- [ ] Supported formats: `jpg`, `png`, `tiff`, `pdf`
- [ ] TIFF: 16-bit per channel, lossless, with EXIF preserved
- [ ] PNG: 8-bit or 16-bit lossless (configurable), no quality loss
- [ ] PDF: single-image PDF at correct print DPI (default: `300`); multiple images can be batched into one PDF later (see SPEC-022)
- [ ] Optional watermark: if `--watermark <path>` is provided, overlay a semi-transparent PNG logo (bottom-right, 10% width) on JPEG and PNG outputs
- [ ] Output sub-directories: `<output>/web/`, `<output>/client/`, `<output>/print/`
- [ ] Metadata written to all formats via ExifTool (SPEC-015)
- [ ] Unit tests: each format produced, file valid, metadata present

## Technical Notes
- TIFF via Pillow: `img.save(path, format="TIFF", compression="none")` for 16-bit save ensure mode is `I;16` or use `tifffile` library
- PDF via `reportlab` or `img2pdf` (`pip install img2pdf`) — img2pdf is lossless JPEG-in-PDF, minimal overhead
- Watermark via Pillow: `Image.paste(logo, position, logo)` where logo has alpha channel
- Darktable can export TIFF directly — prefer this for RAW inputs to preserve maximum quality

## Implementation Hints
```python
FORMAT_SUBDIR = {"jpg": "web", "png": "client", "tiff": "print", "pdf": "print"}

def export(record, output_dir, formats, options):
    results = {}
    processed = darktable_runner.process(record.path, tmp_tiff, style=options.style)
    img = Image.open(processed)
    for fmt in formats:
        dest = output_dir / FORMAT_SUBDIR[fmt] / f"{record.path.stem}.{fmt}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _save(img, dest, fmt, options)
        results[fmt] = dest
    return results
```
