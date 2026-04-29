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
