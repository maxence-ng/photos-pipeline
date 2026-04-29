---
id: SPEC-024
title: "Performance & GPU Scalability"
status: todo
phase: advanced
epic: performance
priority: medium
effort: L
depends_on: ["SPEC-010"]
---

## User Story
As a high-volume user, I want the pipeline to process hundreds of images quickly using all available CPU cores and optionally a GPU so that large wedding or event shoots complete in minutes rather than hours.

## Acceptance Criteria
- [ ] All CPU-bound tasks (culling, thumbnail scoring) run in a `ProcessPoolExecutor` (default: `cpu_count // 2` workers)
- [ ] Darktable CLI calls parallelised with `ThreadPoolExecutor` (I/O-bound; Darktable is multi-threaded internally)
- [ ] NIMA scoring uses batched GPU inference when `torch.cuda.is_available()` (batch size: 32)
- [ ] `--threads <n>` CLI flag and `"threads": N` API parameter override parallelism
- [ ] Benchmark target: **100 JPEG images** culled + scored in < 60 s on a 4-core/8-thread machine (no GPU)
- [ ] Memory usage stays below 4 GB for a 500-image batch (process images in streaming chunks)
- [ ] Progress reporting works correctly under parallel execution (thread-safe counter)
- [ ] `photos-pipeline benchmark --input <dir>` command prints per-stage timing

## Technical Notes
- `ProcessPoolExecutor` for CPU work avoids Python GIL; use for blur/pHash/EAR detection
- Do NOT use multiprocessing for Darktable — it spawns its own processes; use threads with a semaphore to limit concurrent Darktable instances (max: `min(threads, 4)`)
- Streaming chunks: process N images at a time (default: `chunk_size = 50`) to bound memory usage
- Profile with `py-spy` or `cProfile` before optimising

## Implementation Hints
```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_culling_parallel(records: list[ImageRecord], workers: int) -> list[ImageRecord]:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(cull_single, r): r for r in records}
        results = []
        for f in as_completed(futures):
            results.append(f.result())
    return results
```
