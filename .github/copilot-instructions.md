# Copilot Instructions — photos-pipeline

## Project Status

This repository is in the **pre-implementation planning phase**. The only content is a PRD and 24 spec files in `project-planning/specs/`. No Python, Docker, or web source files exist yet. Implementation follows the specs in dependency order starting from SPEC-001.

## Architecture Overview

An automated photo post-processing pipeline with four processing stages in sequence:

1. **Ingestion** (`src/photos_pipeline/modules/ingestion.py`) — scans input folder, produces `ImageRecord` objects with metadata and low-res thumbnails
2. **Culling** (`src/photos_pipeline/modules/culling/`) — removes blur (Laplacian variance), duplicates (pHash), closed eyes (OpenCV), then picks the best from burst sequences
3. **Correction** (`src/photos_pipeline/modules/correction/`) — Darktable CLI applies style presets and auto exposure/WB; intelligent crop centres on detected subjects
4. **Export** (`src/photos_pipeline/modules/export/`) — multi-format output (JPEG/PNG/TIFF/PDF) with ExifTool metadata preservation

The **CLI** (`click`-based `photos-pipeline` command) and **FastAPI REST API** are parallel interface layers over the same pipeline orchestrator (`pipeline.py`).

**Web UI** lives in `web/` (React 18 + TypeScript + Vite + shadcn/ui), communicates with the FastAPI backend, and is served as static files via `StaticFiles` mount.

## Repository Layout (to be created per SPEC-001)

```
src/photos_pipeline/
  cli.py            # Click entry point
  config.py         # Pydantic settings
  pipeline.py       # Orchestrator
  modules/
    ingestion.py
    culling/
    scoring/
    correction/
    export/
  utils/
tests/
  conftest.py
  fixtures/         # Synthetic images (generated, not real photos)
web/
  src/pages/
  src/components/
  src/api/
project-planning/
  photo-pipeline-PRD.md
  specs/            # SPEC-NNN-slug.md — one spec per feature
```

## Build, Test & Lint Commands

These commands are defined by SPEC-001/SPEC-020/SPEC-021 and will apply once the project is set up:

```bash
# Install (editable)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file or test
pytest tests/test_culling.py
pytest tests/test_culling.py::test_blur_detection

# Run only unit tests (skip slow integration/performance tests)
pytest -m unit

# Lint
ruff check src tests

# Type check
mypy src

# Make targets (SPEC-021)
make dev          # install + pre-commit hooks
make test         # pytest + coverage
make build        # package build
make docker-build # build Docker image
```

CI (`ci.yml`) runs `pytest + ruff + mypy` on every push/PR; slow-marked tests are skipped on PRs and only run on merges to `main`.

## Key Conventions

### Spec-driven development
Every feature has a corresponding spec file at `project-planning/specs/SPEC-NNN-slug.md`. Each spec is self-contained and includes acceptance criteria, technical notes, and implementation hints. When implementing a feature, read its spec first. Update `status` in the spec's YAML front-matter (`todo → in-progress → done`) and mirror it in `project-planning/specs/000-INDEX.md`.

### ImageRecord is the pipeline's core data structure
All modules pass `ImageRecord` objects (a `dataclass` or Pydantic `BaseModel`). Ingestion populates it; subsequent modules add fields (e.g., `aesthetic_score`, `is_blurry`, `is_duplicate`). Defer full RAW decode to the correction stage — ingestion only extracts metadata and a small thumbnail (max 800×800).

### External CLI tools wrapped, never called directly
`darktable-cli` and `exiftool` are invoked via dedicated wrapper classes (`DarktableRunner`, `ExifToolHandler`). These classes handle binary discovery, version checks, timeout enforcement, and error parsing. Mock these wrappers (not `subprocess`) in unit tests.

### Python stack
- Python ≥ 3.11, packaged via `pyproject.toml` with `[project.scripts]` entry point
- Core: `opencv-python-headless`, `Pillow`, `numpy`, `rawpy`, `PyTorch`, `click`, `fastapi`, `uvicorn`, `rich`
- Dev: `pytest`, `pytest-cov`, `ruff`, `black`, `pre-commit`, `pytest-mock`, `pytest-asyncio`
- NIMA scorer: MobileNetV2 backbone, weights at `~/.photos_pipeline/models/nima_weights.pth`; CLIP is available as a `--scorer clip` fallback

### API design
- Versioned at `/api/v1/`
- Jobs are async: `POST /api/v1/jobs` enqueues via FastAPI `BackgroundTasks`, poll with `GET /api/v1/jobs/{job_id}`
- All endpoints require `Authorization: Bearer <token>` (SPEC-018)
- In-memory job store for MVP; designed for Redis/DB replacement later

### Testing approach
- Fixture images are **generated synthetically** with Pillow (blur via Gaussian filter, duplicates via copy) — do not commit real photos
- Pytest markers: `unit`, `integration`, `slow`
- CLI tested with Click's `CliRunner`; API endpoints with `httpx.AsyncClient` + `pytest-asyncio`
- Subprocess calls to Darktable/ExifTool are always mocked in unit tests
- Coverage target: ≥ 80% enforced in CI

### Docker
- Multi-stage: `python:3.11-slim` builder → `ubuntu:22.04` runtime
- Runtime includes `darktable` and `libimage-exiftool-perl` installed via apt
- Base OS Ubuntu 22.04 (required for Darktable apt availability)
