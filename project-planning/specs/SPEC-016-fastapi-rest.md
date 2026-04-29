---
id: SPEC-016
title: "FastAPI REST API"
status: todo
phase: intermediate
epic: interface-api
priority: high
effort: L
depends_on: ["SPEC-010"]
---

## User Story
As a SaaS user, I want to submit photos for processing via an HTTP API and poll for results so that I can integrate the pipeline into my own tooling or use it from the Web UI.

## Acceptance Criteria
- [ ] `POST /api/v1/jobs` — start a new job; body: `{ input_dir, output_dir, style, mode, export_formats, cull_options }`; returns `{ job_id, status: "queued" }`
- [ ] `GET /api/v1/jobs/{job_id}` — returns job status, progress (0–100%), log tail, and result URLs when done
- [ ] `GET /api/v1/jobs/{job_id}/results` — returns list of exported file paths/URLs
- [ ] `DELETE /api/v1/jobs/{job_id}` — cancel a running job or delete results
- [ ] `GET /api/v1/presets` — list available style presets
- [ ] `GET /api/v1/health` — liveness probe
- [ ] All endpoints require `Authorization: Bearer <token>` header (see SPEC-018)
- [ ] Jobs run asynchronously (background task via `asyncio` or `BackgroundTasks`)
- [ ] OpenAPI docs auto-generated at `/docs`
- [ ] Unit tests: each endpoint tested with `httpx.AsyncClient` + `pytest-asyncio`

## Technical Notes
- Framework: **FastAPI** with **uvicorn** as ASGI server
- Job state stored in-memory (`dict`) for MVP; can be replaced with Redis/DB later
- For file-based SaaS: `input_dir` is a server-side path for now; file upload endpoint (`POST /api/v1/upload`) is a stretch goal for SPEC-017
- Use `BackgroundTasks` from FastAPI for simple async job execution (Celery overkill for MVP)

## Implementation Hints
```python
from fastapi import FastAPI, BackgroundTasks, Depends
app = FastAPI(title="Photos Pipeline API", version="1.0")

@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(payload: JobRequest, bg: BackgroundTasks, user=Depends(get_current_user)):
    job = JobManager.create(payload)
    bg.add_task(run_pipeline, job)
    return job
```
