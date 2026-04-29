---
id: SPEC-023
title: "User Feedback & Model Fine-tuning"
status: todo
phase: advanced
epic: scoring
priority: medium
effort: XL
depends_on: ["SPEC-007", "SPEC-017"]
---

## User Story
As a power user, I want to rate the exported photos so that the aesthetic scoring model learns my personal style over time and makes increasingly relevant selections.

## Acceptance Criteria
- [ ] Results page (SPEC-017) shows a star rating widget (1–5 stars) per exported image
- [ ] `POST /api/v1/jobs/{job_id}/feedback` accepts `{ image_filename, rating }` (1–5)
- [ ] Feedback data stored in DB with `user_id`, `image_path`, `rating`, `predicted_score`, `timestamp`
- [ ] `photos-pipeline finetune --user-id <id>` CLI command triggers a fine-tuning run using that user's feedback as additional training data
- [ ] Fine-tuned model saved as `~/.photos_pipeline/models/nima_finetuned_<user_id>.pth`
- [ ] Fine-tuning uses PyTorch with a small learning rate (1e-5) on the NIMA backbone; only the last 2 layers unfrozen
- [ ] Requires minimum **50 rated images** before fine-tuning can be triggered
- [ ] Fine-tuning completes in < 5 min on CPU for 50 images
- [ ] Unit tests: feedback endpoint stores data; fine-tune runs without error on synthetic data

## Technical Notes
- Training loop: standard `CrossEntropyLoss` or EMD loss on the 10-class NIMA head
- Use `DataLoader` with a small dataset (50–500 images) — not full AVA retraining
- Model versioning: keep last 3 fine-tuned checkpoints per user; use latest by default
- For SaaS: per-user model weights stored in `<storage_root>/<user_id>/models/`

## Data Schema
```sql
CREATE TABLE feedback (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    job_id      TEXT NOT NULL,
    filename    TEXT NOT NULL,
    rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    pred_score  REAL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
