# Contributing

## Getting started

1. Use Python 3.11 or newer.
2. Create a virtual environment.
3. Install the project with development dependencies:

```bash
pip install -e ".[dev]"
pre-commit install
```

## Development workflow

1. Create a topic branch from the latest default branch.
2. Make focused changes that align with the relevant spec in
   `project-planning\specs\`.
3. Keep docs and tests updated with the code you change.
4. Open a pull request with a concise summary of behavior changes.

## Local checks

Run these commands before opening a pull request:

```bash
ruff check src tests
mypy src
pytest -m unit
```

To run the full suite:

```bash
pytest
```

## Specs-first development

This repository follows spec-driven implementation. Before starting a feature:

1. Read the matching spec file in `project-planning\specs\`.
2. Update the spec front-matter status as work progresses.
3. Mirror that status in `project-planning\specs\000-INDEX.md`.

## Reporting issues

When filing a bug, include:

- the expected behavior
- the actual behavior
- reproduction steps
- logs or tracebacks when available

## Code style

- Ruff handles linting and import ordering.
- Black handles formatting.
- Mypy is used for static type checks.
- Keep modules small and explicit; avoid broad exception handling and silent
  fallbacks.
