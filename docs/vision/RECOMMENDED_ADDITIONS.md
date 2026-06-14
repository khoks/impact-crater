# RECOMMENDED_ADDITIONS.md — Gaps the user didn't mention but the product likely needs

> **Status: round 1 grooming closed (E-1.2, 2026-04-26).** Ten seed candidates formalized as A-001..A-010 with verdicts; five new entries added as A-011..A-015. The `knowledge-curator` skill appends to this file whenever a session surfaces a future-looking requirement or gap not already covered.

This file captures features, requirements, and capabilities that are not always explicitly named in [`RAW_VISION.md`](./RAW_VISION.md), but which Claude (or the user, on reflection) thinks the product needs in order to be a credible product.

The point is to surface gaps early so they can be discussed and either accepted (moved into `GROOMED_FEATURES.md` with a phase tag), rejected (logged here as "considered and rejected" with the reason), or deferred (tagged with a phase and a rationale).

---

## Format

Each addition gets a heading with an `A-NNN` ID (monotonically incrementing, never reused), a one-paragraph description, and a discussion section.

```markdown
### A-NNN — <short title> (YYYY-MM-DD)

**Status:** proposed | accepted | rejected | deferred

**Why this matters.** Short paragraph: why the product likely fails or is incomplete without this.

**What it would look like.** One paragraph or a short bullet list — the smallest credible version of the feature.

**Open questions.** Bullets — what we'd need to decide before building.

**Tradeoff against scope.** Honest cost: how much MVP time this would consume vs. the value delivered.
```

---

## Entries

### A-001 — Media library + project model (2026-04-26)

**Status:** accepted — phase **MVP**

**Why this matters.** Without a persistent project unit, every job loses context the moment the user closes the app. D-011 (async job model) and D-012 (1000 photos + 50 videos / 2–5 hr ceiling) both require a durable, named, resumable container.

**What it would look like.** A "project" = one trip / build / event / shoot. Holds: source-media references (or copies), the user's brief, music selection, mode (standard / music-video), effort level, generated metadata, candidate set, narrative ordering, render artifacts, publish history. One project can host one or more jobs (MVP: one job per project; multi-job per project is implied for the live-job v1 feature in A-012).

**Open questions.** Storage layout (directories on disk vs. DB rows vs. both) — deferred to E-1.3.

**Tradeoff against scope.** Foundational; not optional.

**Linked items.** D-011, D-012, A-005, A-010, [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### A-002 — Privacy posture for faces and locations (2026-04-26)

**Status:** accepted — phase **MVP**

**Why this matters.** D-016 (remote-first MVP routing default) means images leave the device by default, which makes the privacy posture for identifiable faces and geo-tagged locations a load-bearing MVP concern. Users need a clear, consent-based control surface before they trust the product with thousands of photos.

**What it would look like.** A default policy on whether identifiable faces and geo-tagged locations get included in payloads to remote VLMs. A user-facing toggle ("strip EXIF GPS before remote calls", "blur faces in remote previews"). A clear visualization of what is being sent off-device. Per-project override.

**Open questions resolved in E-1.3 round 3 (2026-05-03 / D-035):** strip-EXIF default ON; strip-GPS-only as separate toggle (default ON); blur-faces default OFF; per-project posture (per-project, not per-job, at MVP). Plus a novel mechanism: when blur-faces is ON AND a local LLM is available (v1), face-related operations route to local only via the **privacy-sensitive routing extension (N-011)** to ADR-0007. Plug-and-play hook in MVP.

**Tradeoff against scope.** Modest — local face/EXIF handling is well-understood; the UI surface is the main work. Not optional under remote-first.

**Architectural realization.** [`docs/architecture/ADR-0016-privacy-posture-defaults.md`](../architecture/ADR-0016-privacy-posture-defaults.md). Privacy-routing extension to [`ADR-0007`](../architecture/ADR-0007-remote-llm-abstraction.md) routing-config schema.

**Linked items.** D-016, D-035, A-009 (accessibility metadata uses similar local-extraction pipeline), **N-011** (privacy-sensitive operation routing — novel mechanism).

---

### A-003 — Publishing audit log (2026-04-26)

**Status:** accepted — phase **MVP**

**Why this matters.** Every publish to YouTube (D-007) is a public-facing action with consequences. Users need a timestamped record of what was published, when, from which project version, and to which account. Cheap to build; load-bearing for trust and for any future "unpublish" or "reupload" flow.

**What it would look like.** An append-only log per user (cross-project): `{schema_version, timestamp, project_id, snapshot_id, platform, external_id, external_url, response_code, response_summary, render_content_hash, user_approval_token, publish_metadata}`. Visible in the project UI. Exportable.

**Open questions resolved in E-1.3 (D-024 storage; D-032 connector layer):** Persistence layer = append-only JSONL at `~/.impact-crater/audit.jsonl` mirrored in SQLite `audit` table. Signing / tamper-evident → v1. The schema is finalized in ADR-0013.

**Tradeoff against scope.** Small. Worth doing in MVP.

**Architectural realization.** [`docs/architecture/ADR-0006-storage-layout.md`](../architecture/ADR-0006-storage-layout.md) (storage paths) + [`docs/architecture/ADR-0013-connector-layer.md`](../architecture/ADR-0013-connector-layer.md) (entry shape + write trigger).

**Linked items.** D-007, D-011, D-020, D-024, D-032, A-001, A-010.

---

### A-004 — Cost / quota dashboard (2026-04-26)

**Status:** accepted — phase **MVP-lite**, full v1

**Why this matters.** D-013 (effort-level UX with agentic recommendation) already surfaces cost at job time. Users still need a running view of spend across jobs and a hard ceiling so a runaway job can't drain a quota.

**What it would look like (resolved in E-1.3 / D-034):**
- *MVP-lite:* per-job cost preview (D-013) + **dual-cap quota** (total + per-provider, both hard) configured during first-time-setup wizard, no system default. Pre-job + per-stage check; mid-job pause-and-prompt on cap-approach. Per-job `JobCostSummary` with per-tier / per-provider / per-operation breakdown. Cache-savings rollup.
- *v1:* full dashboard — trend over time; per-project budgets; rate-card auto-update from a community-maintained repo.

**Open questions resolved.** Cost catalog = YAML rate cards shipped with the wheel (`config/rate-cards/{provider}-{model}-{version}.yaml`); user manually updates on rate change at MVP-lite; auto-update → v1.

**Tradeoff against scope.** MVP-lite is small (extends D-013 surfacing into a real telemetry stream). Full dashboard is non-trivial — defer.

**Architectural realization.** [`docs/architecture/ADR-0015-resource-accounting.md`](../architecture/ADR-0015-resource-accounting.md).

**Linked items.** D-013, D-016, D-034, A-015, [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### A-005 — Failure-recovery / resume (2026-04-26)

**Status:** accepted — phase **MVP**

**Why this matters.** D-011 (async jobs) and D-012 (2–5 hr wall-clock ceiling) make resume non-negotiable: a 4-hour curation pass cannot lose progress on a laptop sleep, network blip, or VLM provider 5xx. Without this, the success criterion (D-014) is effectively impossible to hit reliably.

**What it would look like.** Each pipeline stage (deterministic pre-filter, metadata extraction, narrative judgment, render, publish-prep) checkpoints to durable storage. Mid-stage progress is per-item (so resuming a metadata-extraction stage skips photos already processed — synergistic with A-011 cache). All stage transitions are idempotent. Network errors retry with exponential backoff. Job state machine has explicit "paused", "running", "failed", "completed" transitions.

**Open questions.** Retry budget / max-attempt policy. User-visible failure UX (defer detailed UX to E-1.4 roadmap).

**Tradeoff against scope.** Significant engineering, but unavoidable.

**Linked items.** D-011, D-012, A-001, A-011, N-007.

---

### A-006 — Multi-version artifact comparison (2026-04-26)

**Status:** deferred — phase **v1**

**Why this matters.** Becomes valuable once the conversational refine loop (D-011 refine-loop opt-in, planned for v2 conversational delivery) is in place. Without refine, there's only one version per job and nothing to compare.

**What it would look like.** When the user requests an edit ("more landscape shots, less faces"), preserve both the previous render and the new one. Side-by-side preview with diff highlighting (which scenes changed, which got cut, which got added).

**Open questions.** Render-storage cost (each version is a full video). How many versions to retain by default (suggest 3, user-configurable). Diff representation for video.

**Tradeoff against scope.** Requires render storage, diff rendering, comparison UI. Worth waiting for refine to mature.

**Linked items.** D-011, D-020, N-003 (project-as-versioned-artifact frames this naturally).

---

### A-007 — Quality floor + user override (2026-04-26)

**Status:** deferred — phase **v1**

**Why this matters.** Worth having a guard that flags artifacts below a quality threshold before publish. But the threshold needs a tuned quality model, which we don't have at MVP (D-009 quality-score is an output of metadata extraction, not yet calibrated against user-perceived quality).

**What it would look like.** Computed quality score on the rendered Story Video; if below threshold, an explicit warning at the publish-approval step (per D-020). User can override with a confirmation. Threshold defaults learned over time per user.

**Open questions.** Score formulation. Whether the threshold is per-platform (YouTube vs. future Instagram).

**Tradeoff against scope.** Requires the quality model first. Reasonable to defer.

**Linked items.** D-009, D-020.

---

### A-008 — Watermark / brand-mark mode (2026-04-26)

**Status:** deferred — phase **v1**

**Why this matters.** Useful for content brands and creators. Not on the MVP critical path (D-006).

**What it would look like.** A user-uploaded watermark or brand-mark image, with position / size / opacity controls; applied at render. Per-project setting.

**Open questions.** Whether animated brand-marks (intro / outro stings) are in v1 or v2.

**Tradeoff against scope.** Cheap to build; just not on the critical path.

**Linked items.** D-006 (artifact = themed video).

---

### A-009 — Accessibility metadata (alt text, captions) (2026-04-26)

**Status:** accepted — phase **MVP-lite**

**Why this matters.** YouTube (D-007) supports automatic captions, but auto-generated captions on user-uploaded video are noticeably lower quality than ones generated from the source media at curation time. Generating at curation lets the user review and edit before publish.

**What it would look like.**
- *MVP-lite:* auto-generate captions from the audio track (and from per-scene metadata for visual context); user reviews and edits in the publish-approval step (D-020).
- *v1:* alt text per scene, per-scene title overlays, user-editable transcript.

**Open questions.** Caption generation tech (deferred to E-1.3). Whether captions are baked into the render or uploaded as a separate sidecar to YouTube (recommend sidecar — matches YouTube's caption track model).

**Tradeoff against scope.** MVP-lite is small if a caption-gen LLM call is added to the pipeline.

**Linked items.** D-007, D-009, D-020.

---

### A-010 — Backup of source media identity (stable IDs) (2026-04-26)

**Status:** accepted — phase **MVP**

**Why this matters.** Load-bearing for A-011 (cross-job analysis cache) and A-003 (publishing audit log). Re-running curation on the same project must give reproducible results, which requires that "the same photo" is identifiable across runs even if the user has moved the file or renamed it.

**What it would look like.** Each ingested media item gets a content-hash ID (e.g. SHA-256 of the file bytes for photos, SHA-256 of frame samples for video) plus a sidecar registry storing the hash → original-path mapping at ingest time. The hash is the canonical ID across the system.

**Open questions.** Hash algorithm choice (SHA-256 is fine; perceptual hash is a separate signal in the dedup stage). Sidecar storage layout (deferred to E-1.3).

**Tradeoff against scope.** Small. Load-bearing.

**Linked items.** A-001, A-003, A-011, N-007.

---

### A-011 — Cross-job analysis reuse via content-addressed cache (2026-04-26)

**Status:** accepted — phase **MVP-lite**, full **v1**

**Why this matters.** A photo analyzed in one job (rich D-009 metadata: tags, embeddings, quality scores, scene boundaries for video) should not be re-analyzed in a later job — that's wasted compute and wasted spend (D-016 remote-first means real dollars). Cross-job reuse is the natural payoff of A-010 (content-addressed IDs) and unlocks meaningful cost savings on overlapping projects.

**What it would look like.**
- *MVP-lite:* hash-keyed metadata cache. When a photo or video scene is encountered with a hash already in cache, the cached metadata is reused instead of re-extracted. Cache scope = single user / single install.
- *v1:* full cross-project reuse semantics — partial-result reuse (e.g., embedding reused even if tags must be recomputed for a new task context), context-specific tag refresh, cache invalidation when the underlying VLM model version bumps.

**Open questions.** Cache schema (N-007 proposes this as a candidate novel mechanism). What tags are task-context-specific vs. reusable. Cache size / eviction policy.

**Tradeoff against scope.** MVP-lite is straightforward (just gate the metadata-extraction stage on a cache lookup keyed by A-010 hash). Full v1 reuse semantics is harder.

**Linked items.** A-010, D-009, D-016, N-007, [`project/tasks/T-1.2.1.2-curation-pipeline-metadata-model.md`](../../project/tasks/T-1.2.1.2-curation-pipeline-metadata-model.md).

---

### A-012 — Live job (2026-04-26)

**Status:** accepted — phase **v1** (with feature flag in MVP architecture)

**Why this matters.** A major product differentiator. A live job is set up *before* a trip / build / event begins. The app continuously watches a media source (smartphone camera roll, OneDrive folder, Google Photos / iCloud shared upload bucket) and continuously curates. A single live job can produce *multiple* outputs (per-location reels + an overall YouTube video + collages per mini-event) and target *multiple platforms*. Critically, live jobs can publish *during* the event (e.g., a daily reel) before the event ends. All conversationally configured at job creation.

**What it would look like.** A "live job" is a project with an open ingest source (cloud folder / camera-roll watcher) plus a multi-output declaration ("I'll be on a 5-day climb. Daily reel to Instagram. Final climb video to YouTube. Collage per summit to my photo blog."). Continuous curation runs in the background. Publish gates fire either on a schedule or on user approval per output.

**Open questions.** Cloud-source authentication (per-source OAuth). Multi-output orchestration model. During-event publish trigger UX.

**Tradeoff against scope.** **Substantial** scope: live-watch + cloud-source ingest + multi-output orchestration + during-event publish gates each adds significant work. Pulling this into MVP would push the 2–5 hr ceiling (D-014) into 2–5 weeks. Hence v1, **but the MVP architecture must leave a clean feature flag** so live-job can land in v1 without a rewrite — specifically, the project / job model (A-001) and the orchestrator (D-017) must be designed for one-or-many jobs per project and one-or-many outputs per job from day one.

**Linked items.** A-001, A-014, D-017, D-019 (mobile = v2 epic, justified partly because A-012's mobile camera-roll watcher is its v1 first touch), N-005 (live-job pattern, novel mechanism), [`project/tasks/T-1.2.1.6-live-job-style-learning-posture.md`](../../project/tasks/T-1.2.1.6-live-job-style-learning-posture.md).

---

### A-013 — Music-video output mode (2026-04-26; section-to-media NL mapping pulled into MVP 2026-05-02)

**Status:** accepted — phase **MVP** (full version, including section-to-media natural-language mapping). *Originally classified as "MVP basic + v1 NL section mapping"; reclassified to full-MVP per D-031 during E-1.3 round-2 grooming.*

**Why this matters.** Distinct from "background music under a curated video" (standard mode), music-video mode treats the music as the primary structure and assembles media around it. Two-mode design from day one keeps the product flexible to user intent without forking the pipeline.

**What it would look like.** At job creation, the user picks "standard" or "music-video" mode. In music-video mode, the user supplies music (per D-018), and the renderer beat-aligns scene cuts to the music structure. The user can also describe in natural language which sections of the music should be built from which media ("intro = scenic shots; chorus = summit footage; bridge = friends laughing; outro = sunset"). The user's NL spec passes verbatim to the Tier-L Opus narrative judge (per ADR-0012); the judge handles the prose natively, no structured-parse stage required.

**MVP scope after reclassification:**
- Beat detection via Madmom; section detection via librosa; cuts snap to a tempo-aware beat grid (per ADR-0012).
- Section-to-media NL mapping is a free-text field at job creation, optional. The Tier-L judge consumes the spec alongside brief + music structure to produce a section-aware `ArcJudgment` with structured `section_mapping`.

**v1 follow-on work (still v1):** royalty-free music starter pack, licensed-library integration, conversational section adjustments via chat ("make the bridge feel more contemplative" — interactive refinement of an already-existing section spec).

**Open questions resolved in E-1.3:** beat-detection tech = Madmom (per ADR-0012, D-030); UX for declaring section-to-media mappings = single optional NL textarea at job creation (per ADR-0012).

**Tradeoff against scope.** The section-to-media NL mapping was reclassified from v1 to MVP because the Opus-tier judge handles the prose natively — adding it to MVP is one prose field on the project, no architectural debt, no extra pipeline stage.

**Linked items.** D-010, D-018, **D-031** (this scope reclassification), ADR-0012 (architectural realization), [`project/tasks/T-1.2.1.3-music-modes-sourcing.md`](../../project/tasks/T-1.2.1.3-music-modes-sourcing.md), [`project/tasks/T-1.3.2.3-adr-0012-music-alignment.md`](../../project/tasks/T-1.3.2.3-adr-0012-music-alignment.md).

---

### A-014 — Reference-media style learning (2026-04-26)

**Status:** accepted — phase **v1**

**Why this matters.** Broader than the "inspiration-link learning" concept in RAW_VISION. The user can upload pre-built media, link to internet content, or pick a previous app creation, and the AI learns its styling, theme, and curation methodology. Becomes the substrate for the theme library that RAW_VISION imagines.

**What it would look like.** A reference is ingested by extracting a structured style descriptor (color palette, pacing, framing, music feel, narrative shape) — that's the N-004 fingerprint mechanism. The descriptor becomes an input to the curation pipeline (D-009) so subsequent jobs match the reference's style. Sources accepted: uploaded files, public URLs (subject to platform ToS — D-005 governance applies), prior projects in the user's library (A-001).

**Open questions.** Style-vector model choice (deferred to E-1.3). Style "match" objective in the curation pipeline. Whether style learning is per-project or global per user (recommend both, with project overriding global).

**Tradeoff against scope.** Requires the style fingerprint mechanism (N-004) plus integration into the curation objective. Material v1 work.

**Linked items.** N-004, A-011 (content-addressed cache amplifies value when re-running with a new style), D-009, [`project/tasks/T-1.2.1.6-live-job-style-learning-posture.md`](../../project/tasks/T-1.2.1.6-live-job-style-learning-posture.md).

---

### A-015 — Effort-level UX with agentic max-permissible recommendation (2026-04-26)

**Status:** accepted — phase **MVP** (L1–L3 + recommendation), full v1 (cost-transparency UI + upgrade-path agent)

**Why this matters.** Formalizes D-013 as a feature entry. Without it, users cannot translate "I have 3000 photos and a Claude API key" into "what should I expect this to cost and how long will it take?" The agentic surface is the product's first real demonstration that the LLM can reason about its own cost/capability profile.

**What it would look like.**
- *MVP:* 3 effort levels (L1, L2, L3) covering up to D-012's 1000 photos / 50 videos envelope. Max-permissible recommendation surfaced after task details + media selection. Hard stops if the configured config can't support the level.
- *v1:* L4 + L5 (up to ~10000 photos / 500 long videos), full cost-transparency UI, agentic upgrade-path explanations.

**Open questions.** Exact level boundaries (calibrated against D-016 routing default cost curves). Whether the agentic copy is templated or per-call generated (recommend templated MVP, per-call v1).

**Tradeoff against scope.** MVP scope is bounded; the recommendation engine reuses the same orchestrator (D-017).

**Linked items.** D-012, D-013, D-016, D-017, A-004, N-006, [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### A-016 — Cheap-first analysis hardening: thumbnails to LLMs + time-bounded scene sampling (2026-06-11)

**Status:** accepted — phase **v1**

**Why this matters.** The user's instinct from the 2026-06-11 session: "analyzing full-scale images and going through the full video will be very slow and expensive — should the app create thumbnails and snapshot videos first?" The architecture already half-agrees: Stage 1 builds 256px + 1024px thumbnails per photo and runs scenedetect ContentDetector per video with 3 representative frames per scene (content-aware sampling — strictly better than fixed every-N-seconds for cut-rich footage). But the expensive halves are not wired together: Stage 2/3 read the FULL-SIZE source bytes (9–12 MB Pixel JPEGs) and ship them to providers per call. The Anthropic client downscales internally to ≤1568px when over budget; the Gemini path uploads the original bytes every time. And a long single-take video (one 10-minute scene) still yields only 3 analyzed frames — under-sampled in exactly the case the user described.

**What it would look like.**
- Stage 2/3 LLM calls consume `thumb_1024` (or a purpose-built ~1568px analysis rendition) instead of source bytes. The cross-job cache keys on the source content_hash + prompt/params — not the uploaded bytes — so this changes nothing about caching and invalidates nothing.
- Scene sampling gains a time floor: scenes longer than ~20s get an extra representative frame per ~5–10s (capped per scene), so single-take footage is no longer summarized by 3 frames. Per-scene metadata then aggregates over frames.
- Upload payload telemetry (bytes-per-job before/after) so the win is measurable.

**Open questions.** Right analysis resolution (1024 vs 1568 — Anthropic's max edge); per-scene frame cap so a 2-hour video can't explode the Tier-S call count; whether video scenes should also get a cheap motion/blur score locally before any LLM call.

**Tradeoff against scope.** Small (the renditions already exist); large win: ~10× upload-bandwidth reduction per job, faster Stage 2/3 wall-clock, lower egress on metered connections. No quality loss at VLM input resolutions.

**Linked items.** ADR-0010, ADR-0011 Stage 1–3, A-011/N-007 (cache unaffected), S-2.9.5.

---

### A-017 — Semantic near-duplicate suppression: best-of-burst selection (2026-06-11)

**Status:** accepted — phase **v1**

**Why this matters.** Real shoots produce retakes: the same pose, same people, same scene, shot 2–5 times with slightly different focus/angle/exposure. Stage 4's pHash clustering (Hamming ≤ 5) only catches near-identical pixels — a retake from one step to the left lands in a different cluster and BOTH copies survive into Stage 5, wasting judge attention and risking visibly-repetitive videos. The user's requirement from 2026-06-11: unless shots are considerably different, keep only the best one; discard lower-quality/lower-impact duplicates from analysis, planning, and the final video.

**What it would look like.**
- Stage 2 already computes and caches an embedding per asset (.npy, content-addressed) — today only its dimensionality is used. Stage 4 adds an embedding-similarity clustering pass (cosine ≥ threshold, e.g. ~0.92, time-windowed to ±2 minutes so genuinely-recurring scenery across days does not collapse) layered on top of pHash.
- Each semantic cluster keeps its best member by the existing combined score (quality + narrative relevance + diversity), annotated `burst_best_of: N`; losers are dropped with filter-log reasons so the cost-transparency UI can show "suppressed 38 retakes."
- Stage 5's prompt gains the `burst_best_of` context so the judge knows a shot represents a moment, not a one-off.

**Open questions.** Threshold calibration against real trip data (the Zion subset is a good fixture: it contains true retake pairs); whether video scenes participate (scene-frame embedding vs photo embedding comparability); user override knob (dedup aggressiveness) in effort-level UX.

**Tradeoff against scope.** Moderate (clustering code + tests; embeddings are already paid for). Directly serves the user's "individual videos must reach acceptable quality before the package feature" gate (D-042).

**Linked items.** ADR-0011 Stage 4, A-007 (quality floor calibration), S-2.9.6, D-042.

---

### A-018 — Auto-derived trip cast: unique-face inventory, group-vs-crowd, coverage analysis (2026-06-11)

**Status:** **analysis half delivered 2026-06-11** (D-044) — detect→embed→cluster→group/crowd→coverage with pluggable backends (gemini default / insightface optional); coverage-repair UI + person naming + the v1.8 LLM-driven refinements remain. (design N-012)

**Why this matters.** N-008's person library is manual: the user enrolls people by picking face photos. For the dump-and-forget workflow the user described on 2026-06-11, the app should figure out the cast itself: scan the full media set, cluster unique faces, infer who is "the group" (recurs across days/locations) versus background crowd (appears once), then use that inventory during curation — including answering "is everyone included in the final video, or did we leave someone out?"

**What it would look like.** Per N-012: face detection (mediapipe, already a dependency) over analysis renditions → face-embedding clustering → frequency/recurrence scoring (appearances × distinct time-windows × distinct locations) → automatic group/crowd split with a review UI (the user can promote/demote) → cast inventory feeds Stage 5 as curation context and Stage 6 emits a coverage report ("Priya appears in 0 selected clips — add one?"). Optionally seeds N-008's library so manual enrollment becomes a confirmation step.

**Open questions.** Privacy class of face embeddings under ADR-0016 (face_data → N-011 local-only routing when blur-faces is ON); minimum appearances before someone counts as group; child-face handling; collision with the existing manual library (merge semantics).

**Tradeoff against scope.** Significant (clustering + review UI + coverage hooks) — hence v1-late/v2. The mediapipe + embedding groundwork already exists from M5.

**Linked items.** N-008, N-012, ADR-0016, N-011, A-002.

---

### A-019 — AI crowd removal: inpaint non-group people out of photos (2026-06-11)

**Status:** proposed — phase **v2+**

**Why this matters.** Tourist-site media is full of strangers. Once A-018 can tell group from crowd, the natural next step the user named: remove the crowd from selected shots with generative inpainting, producing cleaner artifacts.

**What it would look like.** Per-photo opt-in edit in the refine loop ("remove background people"): segmentation masks for non-cast persons (A-018 supplies identity), generative fill (local SDXL-class model on capable GPUs per ADR-0008, or a remote image-editing API), with before/after preview and per-photo accept/reject. Edited copies live beside originals in the snapshot (N-003 immutability — never overwrite source media).

**Open questions.** Authenticity posture (disclose edits in publish metadata?); quality bar for inpainting at 4K; cost per edit; whether this is local-only by default given ADR-0016 (full-resolution face-bearing crops to a remote editing API is a new privacy surface).

**Tradeoff against scope.** Large and dependency-heavy; clearly post-package-MVP. Park at v2+ and revisit when v2 generative integrations (v2.4) land.

**Linked items.** A-018, N-012, ADR-0008, ADR-0016, N-003.

---

### A-020 — The Trip Package: autonomous multi-artifact planner (2026-06-11)

**Status:** accepted — phase **v2** (seeds in v1.2 multi-output orchestration; design N-013; sequencing gate D-042)

**Why this matters.** The user's stated ultimate feature (2026-06-11, verbatim intent): someone returns from a 10-day group trip, dumps thousands of photos and hundreds of videos, and does NOT want to spend time creating videos — they want the app to spend hours and deliver a complete, shareable package: per-location/event videos, reels/shorts of special moments, one overall trip video, and a montage. "Holistic and piecemeal and manageable and comprehensive and granular at the same time." This is the dump-and-delight promise that makes the app lovable; everything else is plumbing toward it.

**What it would look like.** Per N-013, a planning layer ABOVE the existing single-artifact pipeline:
1. **Trip segmentation** — cluster the full media set into events/locations/days/themes using capture time + GPS (requires ingest-side EXIF GPS parsing — currently GPS is only stripped for privacy, never read) + content signals (Stage 2/3 outputs).
2. **Density-driven artifact allocation** — per cluster, score media density × quality × distinctiveness; rich clusters (e.g. a fully-documented Bryce Canyon hike) earn a dedicated video; thin clusters merge with temporal neighbors into combined videos; standout moments queue as reel/short candidates; everything contributes to the overall video + montage.
3. **Package plan as artifact briefs** — the planner emits N artifact briefs (each = brief + media subset + duration + mode + platform target), executed by the existing Stages 1–7 pipeline per artifact, sharing one analysis pass via the A-011 cache (analysis cost is paid once, not N times).
4. **Package preview** — one approval surface listing every artifact with previews; user approves all / some; publishes per ADR-0013 connectors.

**Open questions.** Cost envelope per package (N judge calls — Tier-L × artifact count dominates; package-level effort-level UX needed); planner placement (v2.2 multi-agent harness is the natural home; a deterministic-first planner could pilot in v1.2's multi-output orchestration); per-platform variants (16:9 YouTube vs 9:16 reels) as separate artifacts or render variants; partial-package refine semantics.

**Tradeoff against scope.** The biggest feature on the roadmap. Explicitly gated by D-042: not before single-video quality is mastered (A-016/A-017 and the v1 quality milestones are prerequisites, per the user: "unless the individual videos are acceptable quality, the package feature doesn't make sense — it is built on top of this capability").

**Linked items.** N-013, N-005/A-012 (v1.2 multi-output seed), A-011/N-007 (shared analysis), D-042, ADR-0013, ROADMAP v2.

---

### A-021 — Media chronology: capture-time + GPS extraction and timeline-aware planning (2026-06-11)

**Status:** accepted — phase **mvp-hardening (delivered 2026-06-11)**

**Why this matters.** The 2026-06-11 audit found the app extracted ZERO capture metadata: no EXIF DateTimeOriginal, no filename-timestamp parsing (the files were literally named `PXL_20260405_223121903.jpg` and the time was discarded), no file mtime. EXIF was only ever *read to be stripped* for privacy — including GPS, which was thrown away rather than used. The narrative judge ordered clips purely on LLM-invented `placement_position` with zero time grounding, and `time_of_day` was a pixel guess. Without real chronology a "story" video can run events backwards, and trip segmentation / burst-window dedup / group-recurrence (A-017, A-018, A-020) are all impossible.

**What it would look like (delivered).** A `media/timeline.py` that reconciles capture time across EXIF DateTimeOriginal > filename patterns (Pixel, IMG_/VID_, WhatsApp, Signal, screenshots, dashed) > file mtime, tagging each with `source` + `confidence` (N-014). EXIF GPS is decoded to decimal degrees. Stage 1 persists `capture_timestamp / capture_source / capture_confidence / gps_lat / gps_lon` (migration 003). The capture time flows to Stage 4 and into the Stage 5 judge prompt, which now defaults to a forward-in-time flow unless the brief calls for otherwise. Verified on real Zion media: EXIF datetime + GPS (37.21, -112.94) extracted correctly.

**Open questions.** Video container creation_time (needs ffprobe — currently videos fall back to filename/mtime); timezone normalization across devices; surfacing capture confidence in the UI; reverse-geocoding GPS to place names for the brief.

**Tradeoff against scope.** Small and foundational — pure-Python, reuses the already-present piexif dependency. Unblocks A-017 time-windows, A-018 recurrence, A-020 trip segmentation.

**Linked items.** N-014, A-017, A-018, A-020, D-043, migration 003.

---

### A-022 — Rich-metadata schema enrichment: shot grammar, per-person expression, safety, specialness, obstructions (2026-06-11)

**Status:** accepted — phase **mvp-hardening (delivered 2026-06-11)**

**Why this matters.** The 2026-06-11 audit scored the metadata schema 6/15 of the user's desired fields fully present. Missing entirely: per-person facial expressions, description of non-main people, content-safety level, intrinsic specialness, cinematographic shot type, obstruction/non-value-crowd detection. The planner can't land an emotional peak on a big smile, vary framing, drop a blocked shot, or keep explicit frames out of a shareable artifact if it never extracted those signals.

**What it would look like (delivered).** RichMetadataPhoto gains: `shot_type` (extreme_wide…macro), `main_subjects` (list of {descriptor, expression, prominence} — the people the shot is ABOUT, with their facial expressions), `other_people`, `scenery_description`, `background_description`, `camera_quality_notes` (textual rationale for the quality number), `specialness_score` (brief-independent memorability), `safety_level` (safe/mild/explicit), and `obstruction_level` + `obstruction_notes`. The extraction prompt asks for each; coercion-tolerant before-validators keep malformed LLM output from killing jobs; the summary the judge sees surfaces shot type + subject expressions + specialness + obstructions; Stage 4 drops `explicit` frames at a new safety floor.

**Open questions.** Calibrating `specialness_score` against real usage; whether `safety_level=mild` should be a user-tunable gate; per-person expression accuracy at 1024px analysis resolution; using obstruction_level as a soft penalty in the combined score (currently informational to the judge).

**Tradeoff against scope.** Moderate (additive schema + prompt; every field defaulted so old caches still validate). High leverage for single-video quality (D-042 gate).

**Linked items.** A-021, A-018 (main_subjects feed the cast), D-043.

---

### A-023 — In-app feedback loop: per-phase diagnostics + decision-level feedback capture (2026-06-14)

**Status:** **delivered 2026-06-14** (D-045)

**Why this matters.** The user wants to keep improving the app's video-creation quality with low-friction inputs tied to specific decisions — not vague "make it better" asks. The pipeline already makes thousands of inspectable decisions (Stage 4 keep/drop with reasons, Stage 5 narrative selection + roles, Stage 6 clips, the trip cast), but they were invisible: the user could only see the final video, so feedback could only be coarse. Making each decision visible and feedback-able, and persisting that feedback where a Claude session can pick it up, turns the whole product into a steerable, continuously-improving system.

**What it would look like (delivered).** The pipeline persists a `diagnostics.json` per snapshot (every phase's decisions with media thumbnails). The preview page's "Inspect & give feedback" opens per-phase panels; clicking any decision opens a popup to mark it correct / incorrect / should-be-different with a note. Feedback is stored in a `feedback` table + mirrored to `~/.impact-crater/feedback.jsonl`; `scripts/feedback.py list|show|mark` (documented in CLAUDE.md) lets a Claude session pick it up and act on it, then mark items addressed.

**Open questions / follow-ons.** Live per-phase popups DURING execution (currently post-completion, which covers the need); feedback-driven auto-tuning (aggregate many "this was wrongly dropped" into a threshold change automatically); a feedback inbox UI in-app; linking an addressed item back to the commit that fixed it.

**Tradeoff against scope.** Moderate — built entirely on artifacts the pipeline already produces (no new LLM calls). High leverage: it's the mechanism by which the user's taste (the stated quality bar) gets encoded into the app over time.

**Linked items.** N-015, D-045, A-017/A-018 (whose decisions are the most feedback-rich), D-042 (single-video-quality gate this directly serves).

---

### A-024 — Developer tracker pages: feedback/enhancement tracker + workplan tracker (2026-06-14)

**Status:** **delivered 2026-06-14** (D-047)

**Why this matters.** The developer (the user) needs to visualize, in the app, both (a) every piece of in-app feedback with its full context, and (b) the whole MVP→v1→v2→v3 workplan maintained in `project/`. Without in-app views these live only in the DB / markdown and require shell access to inspect.

**What it would look like (delivered).** Two routes: `/feedback` lists every feedback item (priority-sorted, status-filterable) and expands to full detail — job/project/snapshot, phase + decision_ref, the decision context (media thumbnail + reason + scores), the whole phase's decision strip pulled from the snapshot diagnostics (the flagged shot highlighted), and the page screenshot — with editable status + priority. `/workplan` renders the Initiative→Epic→Story→Task hierarchy grouped/badged by status + phase with status/phase rollups and editable priority. Status on the workplan is read-only (the markdown is canonical, work-tracker-owned); priority edits are stored as `workplan_overrides` and reconciled into the markdown on the next work-tracker pass.

**Open questions / follow-ons.** Writing status changes from the app (currently read-only for workplan); deep-linking a feedback item to the live job page; bulk triage; a combined "what should I work on next" view that merges high-priority feedback + high-priority workplan items.

**Tradeoff against scope.** Moderate — feedback is already DB-native; the workplan view is a read-only markdown parser + an override table. No change to the canonical tracking model.

**Linked items.** A-023, D-045, D-046, D-047.
