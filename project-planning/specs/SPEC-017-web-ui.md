---
id: SPEC-017
title: "Web UI (React)"
status: todo
phase: intermediate
epic: interface-web
priority: medium
effort: XL
depends_on: ["SPEC-016"]
---

## User Story
As a non-technical user, I want a browser-based interface where I can upload photos, configure the pipeline, monitor progress, review results, and download exports.

## Acceptance Criteria
- [ ] **Page: Home** — "New Session" button; list of recent jobs
- [ ] **Page: Upload** — drag-and-drop or folder-picker; shows file count and total size
- [ ] **Page: Configure** — style preset selector (thumbnail previews), mode toggle (auto/manual), cull settings sliders, export format checkboxes
- [ ] **Page: Review** (manual mode only) — grid of thumbnails after culling; user can toggle keep/discard per image; "Proceed to Export" button
- [ ] **Page: Progress** — live progress bar and log stream (WebSocket or SSE)
- [ ] **Page: Results** — gallery of exported images per format with download buttons; culling summary stats
- [ ] Responsive design (works on tablet and desktop)
- [ ] Built with **React 18 + TypeScript + Vite**; UI library: **shadcn/ui** (Tailwind CSS)
- [ ] Communicates with API (SPEC-016) via `fetch`/`axios`
- [ ] No authentication UI required in this spec (covered by SPEC-018)

## Technical Notes
- Server-Sent Events (SSE) preferred over WebSocket for progress streaming — simpler and works through proxies
- File upload: `POST /api/v1/upload` with `multipart/form-data`; server saves to a job-specific temp directory
- Thumbnail display: API serves images from output dir via a static file endpoint `GET /api/v1/files/{job_id}/{filename}`
- Build output served as static files by FastAPI (`StaticFiles` mount)

## Implementation Hints
```
web/
  src/
    pages/
      Home.tsx
      Upload.tsx
      Configure.tsx
      Review.tsx
      Progress.tsx
      Results.tsx
    components/
      ImageCard.tsx
      StylePicker.tsx
      ProgressBar.tsx
    api/
      client.ts        # axios instance with auth header
      jobs.ts
      presets.ts
  vite.config.ts
  tailwind.config.ts
```
