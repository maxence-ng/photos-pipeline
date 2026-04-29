---
id: SPEC-015
title: "ExifTool Metadata Handling"
status: todo
phase: intermediate
epic: export
priority: medium
effort: M
depends_on: ["SPEC-011"]
---

## User Story
As a photographer, I want all exported files to retain original EXIF/IPTC/XMP metadata (GPS, copyright, camera model, capture date) so that my work is properly credited and searchable.

## Acceptance Criteria
- [ ] `MetadataHandler.copy(source: Path, dest: Path)` copies all EXIF/IPTC/XMP tags from source to dest
- [ ] `MetadataHandler.write(dest: Path, tags: dict)` writes/updates specific tags (e.g. `Copyright`, `Artist`, custom `XMP-xmp:Label`)
- [ ] GPS coordinates preserved (do NOT strip location data by default)
- [ ] Pipeline adds a custom tag: `XMP-dc:CreatorTool = "photos-pipeline vX.Y.Z"`
- [ ] If ExifTool not found on PATH, raise `ExifToolNotFoundError` with install instructions
- [ ] Works on JPEG, TIFF, and PNG outputs
- [ ] Unit tests: after copy, destination has same `DateTimeOriginal` and `GPSLatitude` as source

## Technical Notes
- Use the `pyexiftool` Python wrapper (`pip install pyexiftool`) for subprocess-free interaction
- Alternatively: `subprocess.run(["exiftool", "-TagsFromFile", source, "-all:all", dest])` is simpler but requires process spawning
- ExifTool must be installed separately; version ≥ 12.0 recommended
- On Windows: `exiftool.exe` is a single executable; document placement in PATH

## Implementation Hints
```python
import exiftool  # pyexiftool

class MetadataHandler:
    def __init__(self):
        self.et = exiftool.ExifToolHelper()

    def copy(self, source: Path, dest: Path) -> None:
        self.et.execute(f"-TagsFromFile", str(source), "-all:all", str(dest), "-overwrite_original")

    def write(self, dest: Path, tags: dict) -> None:
        args = [f"-{k}={v}" for k, v in tags.items()]
        self.et.execute(*args, str(dest), "-overwrite_original")
```
