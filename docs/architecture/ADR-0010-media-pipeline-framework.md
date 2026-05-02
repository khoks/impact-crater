# ADR-0010 — Media pipeline framework

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-02
**Phase:** scaffolding

## Context

The deterministic media-handling layer runs *before* any LLM sees media: photo/video decoding, perceptual hashing, dedup, scene segmentation, face detection, smart-crop, aspect-ratio handling, and render execution. It is the path everything else cascades through. The MVP scale envelope is 1000 photos + 50 videos per job (D-012) on a desktop-only target (D-019); the pipeline has to be cheap, deterministic, and parallelizable.

Two MVP-relevant nuances surfaced during round-2 grooming:

- **iPhone-default formats matter.** HEIC is iPhone's default capture format; ignoring it forces users to convert manually. RAW formats (CR2/NEF/ARW/DNG/RAF/ORF/RW2) are power-user territory but the dependency cost is small.
- **Face *recognition* (not just detection) significantly enriches narrative-arc judgment.** Knowing "this is the family group" / "this is Alice and the kids" gives N-001 a much sharper signal than "people detected: 4". The user surfaced a novel approach (filed as **N-008**) that obviates the need for a separate face-recognition library: build a per-person library of N face photos, construct a labeled reference-collage at recognition time, and let the vision LLM identify which library people are in the photo via structured output. This piggybacks on the already-running ADR-0007 LLM infrastructure.

## Decision

### Photo decoding

- **JPEG / PNG / WebP / AVIF:** [Pillow](https://pillow.readthedocs.io/) (PIL fork). Industry standard.
- **HEIC / HEIF:** [pillow-heif](https://github.com/bigcat88/pillow-heif). Required because HEIC is iPhone's default capture format; making users convert manually is hostile UX.
- **RAW (CR2, NEF, ARW, DNG, RAF, ORF, RW2, …):** [rawpy](https://github.com/letmaik/rawpy) (libraw bindings). Rendered to 16-bit linear or 8-bit sRGB depending on downstream stage.
- **Working colorspace at metadata extraction:** sRGB. Vision LLMs see consistent colors across the candidate set; original-bit-depth files are preserved for render. Color profile (ICC) preserved end-to-end where the source has one; otherwise sRGB assumed.
- **EXIF / metadata extraction:** [pyexiv2](https://github.com/LeoHsiao1/pyexiv2) for read; the privacy-strip pass (A-002) writes a stripped variant under the project's cache (full original is never modified in place).

### Video decoding

- **Containers / codecs:** ffmpeg via [`ffmpeg-python`](https://github.com/kkroening/ffmpeg-python) (subprocess wrapper). Covers MP4 / MOV / AVI / MKV / WebM / MTS / M2TS.
- **Probe at ingest:** ffprobe → container, codec, duration, resolution, fps, audio streams; persisted in the source-sidecar JSON per ADR-0006.
- **Frame extraction for analysis:** never re-encode the full video at analysis. Per scene (after segmentation), extract 3 representative frames (start / middle / end) as PNG at native resolution; pass those frames to the vision LLM operations.
- **Render encode:** H.264 / yuv420p / AAC at YouTube-friendly defaults (1080p / 30fps for 16:9). Two-pass mode for the final render; one-pass for refine-loop intermediates.
- **Preview proxies:** 720p H.264 generated lazily per snapshot for in-app preview playback.

### Thumbnails

Generated at ingest:

- 256 px JPEG for grid views.
- 1024 px JPEG for detail views.

Cached at `~/.impact-crater/projects/{project_id}/cache/thumbs/{content_hash}.{size}.jpg` (per ADR-0006). Regenerated only on cache miss.

### Perceptual hashing

- **Library:** [imagehash](https://github.com/JohannesBuchner/imagehash). Maintained, fast, well-tested.
- **Algorithms used:** pHash (perceptual) + dHash (difference). pHash is the primary similarity metric; dHash catches near-exact duplicates pHash sometimes misses on near-identical content.
- **Per-photo:** compute both pHash and dHash at ingest; persist in the `media` SQLite row.
- **Per-video scene:** compute pHash on each of the 3 representative frames; the scene's "fingerprint" is the tuple `(pHash_start, pHash_middle, pHash_end)`.

### Dedup posture

**Off by default.** At ingest, the pipeline groups perceptually-similar items (Hamming distance ≤ 5 on pHash) into a "duplicate cluster" and surfaces them as a **suggestion** in the UI: "Found 47 near-duplicates across 12 clusters. Review?" The user explicitly opts-in per cluster or per project. **Auto-removing user-intentional photos is hostile UX**, so the pipeline never silently drops content.

Dedup *clusters* are still passed to Stage 4 of the curation pipeline (ADR-0011), which can use the cluster information to avoid picking 5 near-identical sunset shots even when the user hasn't deduped — the narrative-arc judge gets a "one-from-each-cluster" hint.

### Face detection + person-library recognition (N-008)

**Default face detection:** the vision LLM (per ADR-0007 / ADR-0009 Tier-M `extract_metadata_image`) extracts "people detected" — count, rough positions, demographic notes — as part of the rich-metadata schema (D-009). No separate face-detection library at MVP.

**Face recognition (novel mechanism, N-008):**

- **Person library** in SQLite (extends ADR-0006's schema):
  - `persons` table: `id`, `display_name`, `created_at`, `notes`.
  - `person_face_photos` table: `id`, `person_id`, `content_hash`, `face_crop_bbox` (the crop region inside the source photo), `captured_at`, `is_primary`.
  - Default cap: **5 face photos per person** (configurable per `settings.face_library_photos_per_person`). Range allowed: 3–10. Beyond 10, collage becomes unwieldy.
- **Adding faces** — two paths from the UI:
  - From existing project media: a face-crop-picker in the media-detail view.
  - Direct upload: drag-and-drop a face photo, auto-detect the face crop, label.
- **Reference collage construction** (the core mechanism):
  - For a given recognition call, all library persons are tiled into a single labeled reference image. Layout: 5-cell horizontal strips per person, person name overlaid above each strip. Strips stacked vertically; max ~20 persons per collage (cap on library size or paginate the collage).
  - Cached as `~/.impact-crater/cache/face-library/{library_version_hash}.png`. Library version = `sha256(sorted(person_ids + photo_hashes))`. Collage is regenerated only when the library content changes.
- **Recognition call**:
  - When the rich-metadata extraction (ADR-0011 Stage 3) runs on a photo and the library is non-empty, the prompt receives **two image inputs**: the photo being analyzed AND the reference collage.
  - The structured-output schema gains a `recognized_persons` field: `list[{person_id: str, display_name: str, confidence: float (0..1), bbox_in_photo: BoundingBox | null}]`.
  - The vision LLM returns the matched persons, with confidence scores and (optionally) bounding boxes in the analyzed photo.
- **Confidence handling:**
  - High confidence (≥0.85): used directly downstream by the narrative-arc judge (Stage 5).
  - Mid confidence (0.5–0.85): surfaced to the user in the metadata-review UI for confirmation; not used until confirmed.
  - Low confidence (<0.5): discarded.
- **Cache invalidation:** the cache key for `extract_metadata_image` (per ADR-0007) gains a `library_version_hash` component when the person library is non-empty. Adding a person or adding a face to an existing person invalidates the relevant cached extractions; the cache reuses entries from before-library-existed for photos that don't need person matching.
- **Pre-deletion safeguard:** removing a person from the library invalidates all cached extractions that included that person; the user is warned.

This avoids carrying an embedding-based face-recognition stack (InsightFace / FaceNet / DeepFace) entirely. The vision LLM sees direct photographic evidence of each person and reasons about identity holistically — robust to lighting/angle variation in ways embedding-similarity sometimes isn't.

### Scene segmentation

Already pinned in ADR-0009 (deterministic, no LLM). Restated here for completeness:

- **Library:** [scenedetect](https://github.com/Breakthrough/PySceneDetect) with `ContentDetector` (adaptive threshold).
- **Output:** list of `(start_time, end_time, representative_frame_indices)` per scene, stored in the media-pipeline cache keyed by `(content_hash, scene_detector_version, threshold_setting)`.
- **Scene-count cap per video:** 50 (configurable via settings; effort-level UX surfaces the default). Long videos get the most-distinct scenes via shot-similarity scoring; the rest are dropped.
- **Per-scene representative frames:** 3 (start, middle, end). Extracted as PNG at native resolution, cached at `~/.impact-crater/projects/{project_id}/cache/scenes/{content_hash}/scene-{i}-{position}.png`.

### Smart-crop

- **Library:** [`smartcrop.py`](https://github.com/smartcrop/smartcrop.py). Saliency-CNN-based.
- **Fallback:** center-crop on saliency-detection failure.
- **Face-aware override:** if face detection (above) reports faces, smart-crop's saliency map is biased to keep at least one face fully in frame (face-bbox area treated as high saliency).
- **Aspect ratios at MVP:** 16:9 only (YouTube per D-007). Source 9:16 (smartphone vertical) gets pad-or-letterbox via standard ffmpeg filter; user can opt for blurred-background fill via the effort-level UX.
- **v1 expansion:** when multi-platform publish lands (D-007, A-008), smart-crop produces multiple aspect-ratio variants per photo/scene.

### Render execution

- **In-process Python** spawning ffmpeg subprocesses via the orchestrator's worker pool (per ADR-0005). One ffmpeg subprocess per render task.
- **Concurrency:** max 1 concurrent render per job at MVP. Avoids VRAM/CPU contention with vision-LLM calls if v1 local LLMs are running concurrently.
- **No container / sidecar / external service at MVP.** Adds packaging complexity and ops surface; revisit only if multi-tenant hosted-service mode (v3) actually demands it.
- **Failure mode:** ffmpeg stderr captured; structured `RenderError(stage, ffmpeg_exit_code, stderr_excerpt)` raised; orchestrator records on the snapshot's `plan.json` and surfaces via the cost-transparency UI (A-015).

### Subprocess worker pool

The orchestrator (per ADR-0005) maintains an `asyncio` task pool with:

- **Worker classes** by resource profile: `cpu` (perceptual hash, smart-crop, scene-detect), `ffmpeg` (decode/encode), `network` (LLM calls — managed by the LLM router, not this pool). Per-class concurrency limits configurable.
- **Backpressure:** queue depth surfaced through the UI's job-progress websocket (per ADR-0005) so users see exactly where in the pipeline a job is.
- **Cancellation:** `JobCancelled` exception propagates through the pool; in-flight ffmpeg subprocesses receive SIGTERM (then SIGKILL after grace period). All workers honor cancellation.
- **Resume:** on resume after crash (A-005), the orchestrator reads the snapshot's `plan.json` and re-queues only the work not yet complete.

## Alternatives considered

- **Skip HEIC at MVP.** Rejected — iPhone is the dominant smartphone in the target user demographic; making users convert is unacceptable. pillow-heif's dependency cost is low.
- **Skip RAW at MVP.** Considered. Power-user feature, but rawpy is a single dependency with broad format coverage. Including it costs almost nothing and unlocks a real user segment. Accepted.
- **Auto-remove duplicates at ingest.** Rejected — auto-removing user-intentional photos is hostile UX.
- **InsightFace / FaceNet / DeepFace for face recognition.** Rejected — adds a heavy dependency (some have non-permissive licenses), needs a separate model file, doesn't integrate with the LLM-driven metadata stage. The N-008 reference-collage approach achieves the same outcome with zero new dependencies.
- **GPU-accelerated perceptual hashing (CUDA).** Premature optimization; imagehash on CPU is fast enough at MVP scale (1000 photos in seconds).
- **Container-isolated render (e.g., ffmpeg in a Docker sidecar).** Considered for sandboxing untrusted media. Rejected at MVP — desktop-first, the user's own media is already on their disk; sandboxing adds packaging burden. Revisit in v3 hosted-service mode.
- **moviepy / imageio for video orchestration.** Rejected in favor of direct ffmpeg-python — moviepy has higher overhead and less control over encoder parameters.

## Consequences

- **HEIC + RAW dependencies** (pillow-heif, rawpy) need to be in the install path; both are pip-installable wheels on Windows / macOS / Linux. No native build required for end users.
- **The person library is a UI surface that needs design work.** A dedicated round (post-round-3) lands the UX details; the SQLite schema is locked here.
- **Cache invalidation around the person library is non-trivial.** The `library_version_hash` component on the cache key keeps it correct, but adding photos rapidly to the library (e.g., a session of bulk labeling) can invalidate many cached entries. The orchestrator can detect this and offer to delay invalidation until the labeling session is "done" (a UX optimization, not an architectural change).
- **The reference collage is bounded to ~20 persons.** Beyond that, the collage gets too dense for the vision LLM. Pagination (multiple collage variants per recognition call) is a v1 enhancement.
- **Scene-count cap (50/video) constrains long-form footage.** A 60-minute video gets the most-distinct 50 scenes; the remaining shot-similarity-low scenes are dropped. The effort-level UX (D-013) lets the user raise the cap at MVP.
- **The render pool's max-1-concurrency at MVP is conservative.** Modern multicore desktops can comfortably run 2-3 concurrent ffmpeg encodes. If MVP testing shows render is the bottleneck (vs. LLM calls), bump the concurrency in a follow-up ADR.
- **Privacy posture (A-002) interactions:** the EXIF-strip and face-blur paths run inside this pipeline, on the in-flight image bytes the LLM clients see. The original source media is never modified in place. ADR-0016 (round 3) formalizes the user-facing privacy controls.

## Linked items

- D-009 (curation pipeline shape — this ADR is the deterministic floor), D-012 (scale envelope), D-019 (desktop-only — render runs locally), A-002 (privacy posture — EXIF-strip and face-blur live here), A-005 (failure recovery — pool resume), A-010 (stable IDs — content-hash referenced from the pipeline), A-011 (cross-job cache — pipeline outputs cached), A-015 (cost-transparency UI — render errors surface here).
- ADR-0005 (Python process owns the pool), ADR-0006 (storage paths for thumbnails / scene frames / face library / collage cache), ADR-0007 (vision-LLM operations consume the pipeline outputs), ADR-0009 (per-operation routing — `extract_metadata_image` is the recognition call site).
- Cascades to: ADR-0011 (curation engine consumes the pipeline outputs), ADR-0012 (music alignment uses ffmpeg from this ADR), ADR-0014 (orchestrator harness manages the worker pool), ADR-0016 (privacy posture defaults — face blur + EXIF strip live here).
- Novel mechanism: **N-008** (person-library + reference-collage face recognition) — see [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md).
- Decision-log entry: D-028 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.2.1 in [`project/tasks/`](../../project/tasks/T-1.3.2.1-adr-0010-media-pipeline.md).
