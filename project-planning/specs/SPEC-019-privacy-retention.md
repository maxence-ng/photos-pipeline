---
id: SPEC-019
title: "Image Privacy & Retention Policy"
status: todo
phase: advanced
epic: saas
priority: medium
effort: M
depends_on: ["SPEC-018"]
---

## User Story
As a SaaS user, I want control over how long my photos are stored on the server so that I can comply with my clients' privacy requirements and avoid unexpected storage costs.

## Acceptance Criteria
- [ ] Default retention TTL: **7 days** after job completion (configurable via `RETENTION_DAYS` env var)
- [ ] `RetentionCleaner` background task runs daily and deletes files + DB records for expired jobs
- [ ] Users can manually delete a job and all associated files via `DELETE /api/v1/jobs/{job_id}`
- [ ] Users can configure per-account retention override: `PATCH /api/v1/users/me/settings` with `{ "retention_days": N }` (N = 1–365, or 0 = delete immediately after download)
- [ ] Deletion is **hard delete** — files removed from disk, DB row removed (no soft-delete by default)
- [ ] `GET /api/v1/jobs/{job_id}` includes `expires_at` timestamp
- [ ] A warning email/notification is sent 24 h before deletion (stretch goal; requires email service)
- [ ] No encryption at rest in MVP (local-first deployment; files are protected by OS-level permissions)
- [ ] Unit tests: create job → advance clock past TTL → cleaner runs → files gone

## Technical Notes
- Background task: use APScheduler (`pip install apscheduler`) scheduled daily at 02:00 UTC
- File deletion: `shutil.rmtree(job_dir)` + DB `DELETE WHERE job_id = ...`
- Encryption note: for future cloud deployment, integrating AWS S3 SSE-S3 or GCP CMEK is the recommended path — document this in README as a roadmap item
- OS-level file permissions (user-scoped directories `chmod 700`) provide adequate protection for local-first

## Implementation Hints
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=2)
async def clean_expired_jobs():
    expired = await db.get_jobs_older_than(days=settings.RETENTION_DAYS)
    for job in expired:
        shutil.rmtree(job.storage_path, ignore_errors=True)
        await db.delete_job(job.id)
```
