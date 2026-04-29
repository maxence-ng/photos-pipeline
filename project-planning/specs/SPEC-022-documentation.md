---
id: SPEC-022
title: "Documentation Site (mkdocs)"
status: todo
phase: advanced
epic: testing-docs
priority: low
effort: M
depends_on: ["SPEC-010"]
---

## User Story
As a user or contributor, I want a searchable documentation website covering installation, CLI usage, API reference, and architecture so that I can quickly find answers without reading source code.

## Acceptance Criteria
- [ ] `mkdocs.yml` configured with `mkdocs-material` theme
- [ ] Sections: Getting Started, Installation, CLI Reference, API Reference, Architecture, Contributing, Changelog
- [ ] CLI reference auto-generated from Click docstrings via `mkdocs-click`
- [ ] API reference auto-generated from FastAPI's OpenAPI schema
- [ ] Architecture section includes the Mermaid pipeline diagram from the PRD
- [ ] Published to **GitHub Pages** automatically on merge to `main`
- [ ] `CHANGELOG.md` follows Keep a Changelog format; updated on each release

## Technical Notes
- `pip install mkdocs mkdocs-material mkdocs-click`
- GitHub Pages via `gh-pages` branch: `mkdocs gh-deploy --force` in CI
- Mermaid diagrams rendered client-side via `mkdocs-material`'s built-in Mermaid support (`pymdownx.superfences`)

## docs/ Structure
```
docs/
  index.md           # Home / overview
  installation.md
  quickstart.md
  cli-reference.md   # auto-generated with mkdocs-click
  api-reference.md
  architecture.md    # Mermaid diagrams from PRD
  presets.md         # Style presets guide
  contributing.md
  changelog.md
mkdocs.yml
```
