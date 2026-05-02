# GROOMED_FEATURES.md — Impact Crater feature catalog

> **Status: round 1 grooming closed (E-1.2, 2026-04-26); round-2 redirect 2026-04-28 (D-022) — refine-loop entry point moved from job-creation toggle to post-render offer; cross-cut 2026-05-02 (D-031) — A-013 section-to-media NL mapping reclassified v1 → MVP via E-1.3 round-2 architecture grooming.** Phase-tagged feature catalog populated. **MVP critical artifact = Story Video** (single themed video with background music, published to YouTube). E-1.4 (roadmap) may revise remaining phase tags. Round-1 + round-2 of E-1.3 (architecture grooming) have settled the tech stack; round 3 still pending.

This document is the groomed, phase-tagged view of every feature the product should ship over time. It is the bridge between the user's raw brain dump (`RAW_VISION.md`) and what actually gets built. Every feature here is tagged with a target phase: `mvp`, `mvp-lite`, `v1`, `v2`, or `v3`.

Cross-references:
- `D-NNN` → [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)
- `A-NNN` → [`RECOMMENDED_ADDITIONS.md`](./RECOMMENDED_ADDITIONS.md)
- `N-NNN` → [`NOVEL_IDEAS.md`](./NOVEL_IDEAS.md)
- Project IDs (`I-`, `E-`, `S-`, `T-`) → [`project/`](../../project/)

---

## MVP critical path

**The single thinnest end-to-end slice the product must deliver.** Locked under D-006 (artifact), D-007 (platform), D-014 (success criterion), D-015 (name).

> *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes in a paragraph what kind of YouTube video they want and what kind of music, picks a target duration, and gets a publish-ready **Story Video** to their connected YouTube Studio account within 2–5 hours.*

| Step | Artifact / behavior | Locked by |
|---|---|---|
| 1 | User creates a project; drags media in | D-011, A-001, A-010 |
| 2 | User describes the Story Video they want; supplies music; picks duration; picks mode (standard / music-video); picks effort level | D-006, D-010, D-013, D-018 |
| 3 | App computes max-permissible level + cost preview; user confirms | D-013, A-015 |
| 4 | Job runs async (user free to leave) | D-011, A-005 |
| 5 | Pipeline: deterministic pre-filter → rich metadata extraction → narrative-arc judgment → render with music sync | D-009, N-001, A-013 |
| 6 | Preview-and-approve UI shows the rendered Story Video, with **two clear actions: Approve (primary) and Refine (secondary)** | D-020 (publish-approval-always-on half), D-022 |
| 7 | (Optional) refine pass — user clicks "Refine this result" alongside Approve at the post-render moment; produces a new render and the same offer again | D-011, D-022 |
| 8 | User approves; app publishes to connected YouTube Studio account | D-007, D-020, A-003 |

---

## Themes (phase-tagged)

### 1. Media ingest & project model

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Drag-drop / folder-pick ingest | mvp | Local media in via filesystem | D-019, A-001 |
| Project / job model | mvp | Persistent, named, resumable container | D-011, A-001, N-003 |
| Stable content-hash IDs for media | mvp | Reproducible re-runs; load-bearing for cache | A-010, N-007 |
| Failure-recovery / resume | mvp | Survives sleep, network blips, provider 5xx | D-011, A-005 |
| Cloud-folder ingest (OneDrive / Google Drive) — desktop watcher | mvp (stretch) / v1 | Optional desktop-side watcher; precursor to live-job sources | D-019, A-012 |

### 2. Curation engine

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Hybrid pipeline (deterministic + multimodal-LLM judgment) | mvp | The core algorithm | D-009 |
| Rich per-photo metadata extraction | mvp | Time / people / location / mood / lighting / quality / activity / objects / clothing / pose / tags | D-009 |
| Scene segmentation for video | mvp | Each scene gets the per-photo metadata schema | D-009 |
| File-level video metadata (codec / size / duration) | mvp | Tagged at ingest | D-009 |
| Narrative-arc judgment stage | mvp | LLM-as-narrative-judge over the candidate set | D-009, N-001 |
| Cross-job content-addressed analysis cache | mvp-lite (universal + model-versioned) / v1 (full reuse-class semantics) | Don't re-analyze the same photo across jobs | A-011, N-007 |
| Quality floor + user override | v1 | Quality model needs calibration first | A-007 |
| Reference-media style fingerprint applied to curation objective | v1 | Style influences *what gets selected*, not just render | A-014, N-004 |

### 3. Story Video generation

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Standard mode (background music under curated video) | mvp | The default Story Video mode | D-006, D-010 |
| Music-video sub-mode (full version) | mvp | User-supplied music drives sequencing; cuts beat-snap; section-to-media NL spec consumed by N-001 narrative judge | D-010, A-013, D-031, ADR-0012 |
| Section-to-media natural-language mapping | mvp | "Chorus → summit footage; bridge → rest stop" — passed verbatim to N-001 judge (reclassified from v1 → MVP, D-031) | A-013, D-031, ADR-0012 |
| User-chosen target duration | mvp | Per-job knob | D-014 |
| Music sourcing — user-supplied | mvp | User uploads or links audio file | D-018 |
| Music sourcing — royalty-free starter pack | v1 | Curated catalog ships in-app | D-018 |
| Music sourcing — licensed library integration | v1 | Third-party (e.g., Epidemic-Sound-class) integration | D-018 |
| Music sourcing — generated music | v2 | Suno-style; cost + quality bounds need work | D-018 |

### 4. Effort-level UX & cost surfacing

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Effort levels L1–L3 with max-permissible recommendation | mvp | Translates user intent + config into actionable level | D-013, A-015, N-006 |
| Effort levels L4–L5 | v1 | Higher-scale envelopes | D-013, A-015 |
| Cost-transparency UI | v1 | Running spend by provider / job / operation | A-004, A-015 |
| Upgrade-path agent | v1 | Agentic explanation of what config change unlocks higher levels | A-015, N-006 |
| Per-day spend cap (hard stop) | mvp-lite | Backstop against runaway jobs | A-004 |

### 5. Preview, approve, publish

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Preview-and-approve UI (always on, no opt-out) | mvp | Foundational trust gate; surfaces Approve + Refine as twin actions | D-020 (publish-approval half), D-022 |
| Refine loop (offered post-render, alongside Approve) | mvp | Optional second-place action on the result; not a job-creation toggle | D-011, D-022 |
| Multi-version artifact comparison | v1 | Side-by-side after refine; natural home for comparing original vs. refined renders | A-006, N-003 |
| Publish to YouTube via connected Studio account | mvp | The single MVP platform | D-007 |
| Publishing audit log | mvp | Append-only record per project | A-003 |
| Multi-platform publish (Instagram, Facebook, X) | v1 | One per-platform connector at a time | D-007 |
| Per-platform formatting (aspect ratio, duration) | v1 | Co-arrives with multi-platform | D-007 |

### 6. LLM routing & agent harness

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Remote-first routing default | mvp | Required to hit 2–5 hr ceiling at MVP scale | D-009, D-012, D-016 |
| Routing abstraction in place from day one | mvp | Local-first config flip in v1, not rewrite | D-016 |
| Single orchestrator with structured tool calls | mvp | Hosts the agentic UX surface | D-017 |
| Operation-aware LLM router | v1 | Per-sub-operation routing; gates local-first v1 | D-016, N-002 |
| Local-first routing default | v1 | Config flip + N-002 router | D-016 |
| Multi-agent harness (planner + media-analyst + editor + publisher) | v2 | Co-arrives with conversational refinement at scale | D-017 |

### 7. Privacy, security, accessibility

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Privacy posture for faces and locations (consent / strip-EXIF / blur-faces) | mvp | Required because remote-first sends images off-device | A-002, D-016 |
| Auto-generated captions | mvp-lite | At curation time, user reviews pre-publish | A-009, D-007 |
| Per-scene alt text + user-editable transcript | v1 | Richer accessibility metadata | A-009 |
| Watermark / brand-mark mode | v1 | User-uploaded brand asset, position / size / opacity controls | A-008 |

### 8. Live job (the v1 differentiator)

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Live-job pattern (continuous-ingest + multi-output + during-event publish) | v1 | Set up before event; publishes during it | A-012, N-005 |
| Camera-roll / cloud-bucket ingest sources for live job | v1 | Smartphone camera roll, OneDrive, Google Photos, iCloud | A-012, D-019 |
| Multi-output orchestration (per-location reels + overall video + collages from one source set) | v1 | Multiple outputs from one job | A-012 |
| Multi-platform per-output targeting | v1 | Each output picks its platform | A-012 |
| During-event publish triggers (schedule or user approval) | v1 | Daily reels, per-location collages, etc. | A-012, D-020 |
| Live-job conversational configuration | v1 | Orchestrator negotiates the multi-output plan in natural language | A-012, D-017 |

### 9. Reference-media style learning

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Style fingerprint extraction from reference media | v1 | Color palette, pacing, framing, music feel, narrative shape | A-014, N-004 |
| Reference sources: uploaded files, public URLs, prior projects | v1 | Subject to platform ToS for URL sources | A-014 |
| Style match as a curation objective | v1 | Style influences candidate selection + ordering | A-014, N-004 |
| Theme library (gradually-learned) | v1 | Built on top of reference learning | A-014 |

### 10. Auto photo & video editing

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Auto highlights / shadows / contrast / color grading per scene | v1 | Per RAW_VISION; not on MVP critical path | (RAW_VISION) |

### 11. Conversational refinement & agentic editing dialogue

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Natural-language refine ("more landscape, less faces") | v2 | Co-arrives with multi-agent harness | D-011, D-017 |
| Conversational style adjustments via chat | v2 | "Make this feel more cinematic" | A-014 |

### 12. Mobile

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Mobile UI + camera-roll watcher | v2 | Own epic; first mobile touchpoint is A-012 in v1 | D-019, A-012 |

### 13. Hosted-service mode

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Hosted multi-tenant deployment | v3 | Per CLAUDE.md mission; config flip on the self-hosted-first design | (CLAUDE.md) |

---

## Project as a versioned artifact (cross-cutting)

N-003 reframes the entire project / job storage layer as a content-addressed DAG of snapshots. This is **not its own theme** — it is a substrate that makes A-006 (multi-version comparison), A-003 (publishing audit log), and A-012 (live-job multi-output orchestration) cleaner. Phase: aligned with whichever consumer feature lands first; concrete schema goes through E-1.3.

---

## Out of MVP scope (explicit)

To keep the MVP honest, the following are **explicitly NOT in MVP** even though they appear in this catalog:

- Multiple artifact types in one job (only Story Video in MVP — D-006).
- Multiple platforms in one publish (only YouTube in MVP — D-007).
- Live-job pattern (v1 — A-012).
- Reference-media style learning (v1 — A-014).
- Local-first LLM routing default (v1 — D-016).
- Auto photo / video editing (v1).
- Mobile UI (v2 — D-019).
- Multi-agent harness (v2 — D-017).
- Conversational refinement at scale (v2).

Anything that doesn't appear in the MVP rows above is automatically v1+ unless the team explicitly promotes it during E-1.4 roadmap grooming.

---

## Pending (round 2 of E-1.2, if needed; otherwise carries to E-1.4)

- [ ] Tech-stack-independent acceptance tests for each MVP-tagged feature row above (E-1.3 will tie these to chosen tech).
- [ ] First-pass effort estimate per MVP feature (E-1.4 will turn into a concrete schedule).
- [ ] Per-feature owner / story decomposition (created on-demand by `work-tracker` as work begins).
