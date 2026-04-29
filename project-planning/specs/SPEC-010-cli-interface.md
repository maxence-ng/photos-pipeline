---
id: SPEC-010
title: "Basic CLI Interface"
status: todo
phase: mvp
epic: interface-cli
priority: high
effort: M
depends_on: ["SPEC-003", "SPEC-004", "SPEC-007", "SPEC-008"]
---

## User Story
As a photographer, I want a simple command-line tool that runs the full pipeline on a folder of photos with a single command so that I can automate post-processing without a UI.

## Acceptance Criteria
- [ ] Entry point: `photos-pipeline` (installed via pip)
- [ ] `photos-pipeline process --input <dir> --output <dir>` runs the full pipeline
- [ ] `--mode auto` (default) runs everything non-interactively; `--mode manual` pauses after culling to allow user review before correction/export
- [ ] `--style <name>` selects a style preset (default: `natural`)
- [ ] `--no-cull` skips the culling stage
- [ ] `--export jpg png tiff` selects output formats (default: `jpg`)
- [ ] `--threads <n>` controls parallelism (default: `cpu_count // 2`)
- [ ] `--blur-threshold <float>` overrides the blur detection threshold
- [ ] Progress bar (via `rich` or `tqdm`) shows per-image progress
- [ ] End-of-run summary printed to stdout: images processed, culled (per reason), exported
- [ ] Exit code `0` on success, `1` on error
- [ ] `photos-pipeline --version` prints version from `pyproject.toml`
- [ ] Unit tests: CLI invoked with `CliRunner` (Click test utility), mocking pipeline steps

## Technical Notes
- Use `click` for argument parsing
- Use `rich` for coloured console output and progress bar
- `photos-pipeline ingest` can be a sub-command for ingestion-only preview (lists files found, no processing)

## Implementation Hints
```python
import click
from rich.progress import track

@click.group()
@click.version_option()
def cli(): pass

@cli.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True))
@click.option("--output", "-o", required=True, type=click.Path())
@click.option("--mode", type=click.Choice(["auto", "manual"]), default="auto")
@click.option("--style", default="natural")
@click.option("--no-cull", is_flag=True)
@click.option("--export", multiple=True, default=["jpg"])
@click.option("--threads", type=int, default=None)
@click.option("--blur-threshold", type=float, default=100.0)
def process(input, output, mode, style, no_cull, export, threads, blur_threshold):
    ...
```
