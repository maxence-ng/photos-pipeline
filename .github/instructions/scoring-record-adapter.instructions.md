---
description: Preserve the record-oriented scoring adapter contract.
applyTo: "src/photos_pipeline/modules/scoring/records.py"
---

## Record scoring adapter
- Keep `ImageRecordScorer` as a thumbnail-to-backend adapter: extract `record.thumbnail` and delegate batched inference to an `AestheticScorer` via `score_batch()`.
- `score()` and `process()` should stay thin wrappers over the batch methods.
- Persist each returned score on `record.aesthetic_score`; `process()` and `process_batch()` should return the same mutated record objects.
- When any record lacks a thumbnail, raise `ValueError(f"No thumbnail available for {record.path}")` before calling the backend.
