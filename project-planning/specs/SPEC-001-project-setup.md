---
id: SPEC-001
title: "Project Setup & Infrastructure"
status: done
phase: mvp
epic: infrastructure
priority: high
effort: M
depends_on: []
---

## User Story

As a developer, I want a well-structured Python project repository with CI, licensing, and containerisation foundations so that all contributors can onboard quickly and every commit is validated automatically.

## Acceptance Criteria

- [x] Repository follows `src/` layout: `src/photos_pipeline/`, `tests/`, `docs/`, `project-planning/`
- [x] `pyproject.toml` (or `setup.cfg`) defines package metadata, dependencies, and entry point `photos-pipeline`
- [x] `LICENSE` file contains Apache 2.0 text
- [x] `README.md` covers installation, quick-start, and contribution guide
- [x] `.gitignore` covers Python, IDE artifacts, RAW files, and large model weights (`*.pt`, `*.pth`)
- [x] GitHub Actions workflow runs `pytest` + `ruff` lint on every push and PR
- [x] `pre-commit` config included (ruff, black, mypy optional)
- [x] `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` present

## Technical Notes

- Python ≥ 3.11
- Core dependencies: `opencv-python-headless`, `Pillow`, `numpy`, `rawpy`, `PyTorch` (cpu extra), `click` (CLI), `fastapi`, `uvicorn`
- Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `black`, `pre-commit`
- Use `pyproject.toml` with `[project.scripts]` entry point

## Implementation Hints

```text
src/
  photos_pipeline/
    __init__.py
    cli.py          # Click entry point
    config.py       # Pydantic settings
    pipeline.py     # Orchestrator
    modules/
      ingestion.py
      culling/
      scoring/
      correction/
      export/
    utils/
tests/
  conftest.py
  fixtures/         # Small test images (blur, sharp, duplicate pairs)
```
