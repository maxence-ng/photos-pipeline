---
id: SPEC-002
title: "Ingestion Module"
status: todo
phase: mvp
epic: ingestion
priority: high
effort: M
depends_on: ["SPEC-001"]
---

## User Story
As a user, I want the pipeline to scan an input folder and load all supported photo files (RAW and JPEG) so that subsequent modules receive a consistent image list with metadata.

## Acceptance Criteria
- [ ] `Ingester` class accepts a directory path and returns a list of `ImageRecord` objects
- [ ] Supported extensions: `.orf`, `.cr2`, `.nef`, `.raf`, `.arw`, `.rw2`, `.jpg`, `.jpeg` (case-insensitive)
- [ ] Each `ImageRecord` contains: `path`, `format` (raw|jpeg), `camera_make`, `camera_model`, `capture_datetime`, `width`, `height`
- [ ] RAW metadata extracted via `rawpy` + `exifread`; JPEG via `Pillow`
- [ ] Recursive scan option (`--recursive` flag)
- [ ] Files with unsupported extensions are logged as warnings and skipped
- [ ] Unit tests with fixture images covering each supported RAW brand and a JPEG

## Technical Notes
- Use `rawpy` to open RAW files (supports ORF natively via LibRaw)
- Use `exifread` for EXIF extraction on both RAW and JPEG
- `ImageRecord` should be a `dataclass` or Pydantic `BaseModel`
- Defer full RAW decode (expensive) to correction stage; ingestion only reads metadata + generates a quick JPEG thumbnail for culling

## Implementation Hints
```python
@dataclass
class ImageRecord:
    path: Path
    format: Literal["raw", "jpeg"]
    camera_make: str
    camera_model: str
    capture_datetime: datetime | None
    width: int
    height: int
    thumbnail: np.ndarray | None  # low-res RGB for culling
```
Generate thumbnail with `rawpy.extract_thumb()` for RAW, `Pillow.thumbnail()` for JPEG (max 800×800).
