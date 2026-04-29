---
id: SPEC-021
title: "Docker & CI/CD Deployment"
status: todo
phase: advanced
epic: infrastructure
priority: high
effort: M
depends_on: ["SPEC-001"]
---

## User Story
As a developer or operator, I want the application to be fully containerised and automatically built/tested on every commit so that deployments are reproducible and reliable.

## Acceptance Criteria
- [ ] `Dockerfile` (multi-stage): builder stage installs Python deps; runtime stage includes Darktable CLI, ExifTool, and the application
- [ ] `docker-compose.yml` spins up the API server + optional PostgreSQL (profile: `full`)
- [ ] GitHub Actions workflow `ci.yml`: on push/PR → `pytest` + `ruff` + `mypy`
- [ ] GitHub Actions workflow `release.yml`: on tag `v*` → build Docker image → push to GHCR (GitHub Container Registry)
- [ ] `Makefile` with targets: `make dev`, `make test`, `make build`, `make docker-build`
- [ ] `.env.example` documents all required environment variables
- [ ] README includes "Quick Start with Docker" section
- [ ] Docker image size < 2 GB (use Darktable headless package)

## Technical Notes
- Base image: `ubuntu:22.04` (Darktable available via apt `darktable`)
- Darktable in Docker: `RUN apt-get install -y darktable` (includes CLI)
- ExifTool: `RUN apt-get install -y libimage-exiftool-perl`
- Python deps in a virtual environment inside the image for cleaner layering
- Multi-arch build (`linux/amd64`, `linux/arm64`) is a stretch goal

## Implementation Hints
```dockerfile
# --- Builder stage ---
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && pip install --no-cache-dir .

# --- Runtime stage ---
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    darktable libimage-exiftool-perl python3.11 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /app /app
ENTRYPOINT ["photos-pipeline"]
```
