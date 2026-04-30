# photos-pipeline

`photos-pipeline` is an automated photo post-processing pipeline for ingesting,
culling, correcting, and exporting batches of images.

## Status

The repository now contains the project scaffolding for the pipeline. The core
processing logic is implemented incrementally from the specs in
`project-planning\specs\`, starting with `SPEC-001`.

## Installation

1. Create and activate a Python 3.11+ virtual environment.
2. Install the project in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

## Quick start

### CLI

The Click entry point is installed as `photos-pipeline`:

```bash
photos-pipeline --help
```

### API

The FastAPI service is added in later specs. This setup phase only provides the
shared Python package and initial configuration surface.

## Configuration

Key pipeline settings are controlled via environment variables (see `src/photos_pipeline/config.py`).

| Variable | Default | Description |
|---|---|---|
| `PHOTOS_PIPELINE_BLUR_THRESHOLD` | `100.0` | Laplacian variance threshold for blur detection. Images whose variance falls below this value are flagged as blurry and culled. |

**Tuning `PHOTOS_PIPELINE_BLUR_THRESHOLD`:** The right value depends on your equipment and shooting conditions. Start with the default (`100.0`) and inspect which images get flagged. Raise the threshold if soft-focus shots from a slow zoom or kit lens are being let through; lower it if sharp primes are incorrectly flagged as blurry. There is no universally correct value — treat it as a per-camera-body/lens calibration step.

## Development

Run the standard project checks locally:

```bash
ruff check src tests
mypy src
pytest
```

Install and enable pre-commit hooks:

```bash
pre-commit install
pre-commit run --all-files
```

## Contributing

See `CONTRIBUTING.md` for the local workflow, checks, and pull request
expectations.

## License

This project is licensed under the Apache License 2.0. See `LICENSE`.
