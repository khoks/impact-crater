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

**Open questions.** Default value (strip / don't strip)? Tech-stack choice for face detection runs locally (E-1.3). Whether the privacy posture is global, per-project, or per-job (recommend per-project at MVP).

**Tradeoff against scope.** Modest — local face/EXIF handling is well-understood; the UI surface is the main work. Not optional under remote-first.

**Linked items.** D-016, A-009 (accessibility metadata uses similar local-extraction pipeline).

---

### A-003 — Publishing audit log (2026-04-26)

**Status:** accepted — phase **MVP**

**Why this matters.** Every publish to YouTube (D-007) is a public-facing action with consequences. Users need a timestamped record of what was published, when, from which project version, and to which account. Cheap to build; load-bearing for trust and for any future "unpublish" or "reupload" flow.

**What it would look like.** A append-only log per project: `{timestamp, artifact_id, version_hash, target_platform, target_account, video_url, publisher_action_id}`. Visible in the project UI. Exportable.

**Open questions.** Persistence layer (deferred to E-1.3 storage decision). Whether the log is signed / tamper-evident at MVP (recommend simple append-only, signing → v1).

**Tradeoff against scope.** Small. Worth doing in MVP.

**Linked items.** D-007, D-011, D-020, A-001, A-010.

---

### A-004 — Cost / quota dashboard (2026-04-26)

**Status:** accepted — phase **MVP-lite**, full v1

**Why this matters.** D-013 (effort-level UX with agentic recommendation) already surfaces cost at job time. Users still need a running view of spend across jobs and a hard ceiling so a runaway job can't drain a quota.

**What it would look like.**
- *MVP-lite:* per-job cost preview (already in D-013) + a per-day spend cap with a hard stop.
- *v1:* full dashboard — running spend by provider, by job, by operation; trend over time; per-project budgets.

**Open questions.** Whose cost catalog is canonical (per-provider price scraping vs. user-entered)? Recommend user-entered at MVP-lite, automatic in v1.

**Tradeoff against scope.** MVP-lite is small (extends D-013 surfacing). Full dashboard is non-trivial — defer.

**Linked items.** D-013, D-016, A-015, [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

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
