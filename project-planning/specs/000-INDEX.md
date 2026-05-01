# Photos-Pipeline — Backlog Index

> AI-spec-driven backlog. Each row links to a detailed spec file.  
> Status is mirrored in the YAML front-matter of each file and **this table is the single source of truth for quick scanning**.

---

## How to use

- **Update status** in the spec file front-matter (`status: todo → in-progress → done`), then mirror it here.
- **Add a spec** by creating `SPEC-NNN-slug.md` following the template below and inserting a row.
- Each spec is self-contained: an AI agent or a developer can implement it by reading only that file.

### Status legend
| Symbol | Meaning |
|--------|---------|
| ⬜ | `todo` |
| 🔵 | `in-progress` |
| ✅ | `done` |
| 🔴 | `blocked` |

---

## Phase 1 — MVP

| Status | ID | Title | Epic | Priority | Effort | Depends on |
|--------|----|-------|------|----------|--------|------------|
| ✅ | [SPEC-001](SPEC-001-project-setup.md) | Project Setup & Infrastructure | infrastructure | high | M | — |
| ✅ | [SPEC-002](SPEC-002-ingestion-module.md) | Ingestion Module | ingestion | high | M | SPEC-001 |
| ✅ | [SPEC-003](SPEC-003-blur-detection.md) | Blur Detection (Laplacian) | culling | high | S | SPEC-002 |
| ✅ | [SPEC-004](SPEC-004-duplicate-detection.md) | Duplicate Detection (pHash) | culling | high | S | SPEC-002 |
| ⬜ | [SPEC-005](SPEC-005-closed-eye-detection.md) | Closed-Eye Detection | culling | medium | M | SPEC-002 |
| ✅ | [SPEC-006](SPEC-006-burst-selection.md) | Burst Shot Selection | culling | medium | M | SPEC-003 |
| ✅ | [SPEC-007](SPEC-007-aesthetic-scoring.md) | Aesthetic Scoring (NIMA) | scoring | high | L | SPEC-002 |
| 🔵 | [SPEC-008](SPEC-008-darktable-cli.md) | Darktable CLI Integration | correction | high | M | SPEC-002 |
| ⬜ | [SPEC-009](SPEC-009-style-presets.md) | Style Presets Management | correction | high | M | SPEC-008 |
| ⬜ | [SPEC-010](SPEC-010-cli-interface.md) | Basic CLI Interface | interface-cli | high | M | SPEC-003, SPEC-004, SPEC-007, SPEC-008 |
| ⬜ | [SPEC-011](SPEC-011-jpeg-export.md) | JPEG Export (basic) | export | high | S | SPEC-008 |

## Phase 2 — Intermediate

| Status | ID | Title | Epic | Priority | Effort | Depends on |
|--------|----|-------|------|----------|--------|------------|
| ⬜ | [SPEC-012](SPEC-012-auto-exposure-wb.md) | Auto Exposure & WB Correction | correction | medium | M | SPEC-008 |
| ⬜ | [SPEC-013](SPEC-013-intelligent-crop.md) | Intelligent Crop | correction | medium | L | SPEC-008 |
| ⬜ | [SPEC-014](SPEC-014-multiformat-export.md) | Multi-Format Export (PNG/TIFF/PDF) | export | medium | M | SPEC-011 |
| ⬜ | [SPEC-015](SPEC-015-exiftool-metadata.md) | ExifTool Metadata Handling | export | medium | M | SPEC-011 |
| ⬜ | [SPEC-016](SPEC-016-fastapi-rest.md) | FastAPI REST API | interface-api | high | L | SPEC-010 |
| ⬜ | [SPEC-017](SPEC-017-web-ui.md) | Web UI (React) | interface-web | medium | XL | SPEC-016 |
| ⬜ | [SPEC-018](SPEC-018-saas-auth.md) | SaaS Multi-User & Auth | saas | high | L | SPEC-016 |

## Phase 3 — Advanced

| Status | ID | Title | Epic | Priority | Effort | Depends on |
|--------|----|-------|------|----------|--------|------------|
| ⬜ | [SPEC-019](SPEC-019-privacy-retention.md) | Image Privacy & Retention Policy | saas | medium | M | SPEC-018 |
| ⬜ | [SPEC-020](SPEC-020-test-suite.md) | Full Test Suite | testing-docs | high | L | SPEC-010, SPEC-014 |
| ⬜ | [SPEC-021](SPEC-021-docker-cicd.md) | Docker & CI/CD Deployment | infrastructure | high | M | SPEC-001 |
| ⬜ | [SPEC-022](SPEC-022-documentation.md) | Documentation Site (mkdocs) | testing-docs | low | M | SPEC-010 |
| ⬜ | [SPEC-023](SPEC-023-feedback-finetuning.md) | User Feedback & Model Fine-tuning | scoring | medium | XL | SPEC-007, SPEC-017 |
| ⬜ | [SPEC-024](SPEC-024-performance-scalability.md) | Performance & GPU Scalability | performance | medium | L | SPEC-010 |

---

## Spec file template

```markdown
---
id: SPEC-NNN
title: "Feature Name"
status: todo        # todo | in-progress | done | blocked
phase: mvp          # mvp | intermediate | advanced
epic: culling       # infrastructure | ingestion | culling | scoring | correction | export
                    # interface-cli | interface-api | interface-web | saas | testing-docs | performance
priority: high      # high | medium | low
effort: M           # S (<1d) | M (1-3d) | L (3-7d) | XL (>7d)
depends_on: []
---

## User Story
As a [role], I want [goal] so that [benefit].

## Acceptance Criteria
- [ ] ...

## Technical Notes
...

## Implementation Hints
...
```
