# GROOMED_FEATURES.md — Impact Crater feature catalog

Impact Crater is a dead-simple 1-click media-to-video creator: the user dumps a pile of photos and videos, describes in their own words the video(s) they want and where to post them, clicks submit, and is done — the AI prepares, plans, curates, synthesizes, and (after one preview-and-approve gate) publishes. Everything catalogued below is the **internal feature catalog** that delivers that single experience; the user never operates these features individually.

> **Status: round 1 grooming closed (E-1.2, 2026-04-26); round-2 redirect 2026-04-28 (D-022) — refine-loop entry point moved from job-creation toggle to post-render offer; cross-cut 2026-05-02 (D-031) — A-013 section-to-media NL mapping reclassified v1 → MVP via E-1.3 round-2 architecture grooming.** Phase-tagged feature catalog populated. **MVP critical artifact = Story Video** (single themed video with background music, published to YouTube). E-1.4 (roadmap) may revise remaining phase tags. Round-1 + round-2 of E-1.3 (architecture grooming) have settled the tech stack; round 3 still pending. **2026-10-25 (restart audit, D-057):** the **delivered** markers below were refreshed against the code and the tracker — the MVP critical artifact (a Story Video) has been delivered to the preview gate on a real 1,663-asset trip (2026-06-18), and the 2026-06-11 → 2026-07-01 hardening work (chronology + rich metadata, trip cast, feedback loop, curation quality, output polish, open-ended refinement) carries dated markers in the themes; **publishing has never been exercised** — dry-run default, env-var credentials, audit table empty — and is the one open MVP gate. Rows whose phase cell is a plain tag (`mvp`, `v1`, …) describe intent, not delivery; where a tagged row is only partly real, the row says which part.

This document is the groomed, phase-tagged view of every feature the product should ship over time. It is the bridge between the user's raw brain dump (`RAW_VISION.md`) and what actually gets built. Every feature here is tagged with a target phase: `mvp`, `mvp-lite`, `v1`, `v2`, or `v3`.

**Subordinate qualities in service of one-click.** Several catalogued capabilities — it **learns** from feedback, **tracks** jobs, runs **efficiently**, is hardware/quota-**adaptive**, **caches** analysis across jobs, keeps a **person library / trip cast**, and will one day deliver the **Trip Package** — are real and valuable, but strictly subordinate to the headline. They exist to make the single dump → describe → submit → done loop faster, cheaper, and more personal; they are never the product's identity.

Cross-references:
- `D-NNN` → [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)
- `A-NNN` → [`RECOMMENDED_ADDITIONS.md`](./RECOMMENDED_ADDITIONS.md)
- `N-NNN` → [`NOVEL_IDEAS.md`](./NOVEL_IDEAS.md)
- Project IDs (`I-`, `E-`, `S-`, `T-`) → [`project/`](../../project/)

---

## MVP critical path

> *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes in a paragraph what kind of YouTube video they want and what kind of music, picks a target duration, and gets a publish-ready **Story Video** to their connected YouTube Studio account within 2–5 hours.*

**The single thinnest end-to-end slice the product must deliver** — one dump, one description, one submit, done. Locked under D-006 (artifact), D-007 (platform), D-014 (success criterion), D-015 (name).

| Step | Artifact / behavior | Locked by |
|---|---|---|
| 1 | User creates a project; drags media in | D-011, A-001, A-010 |
| 2 | User describes the Story Video they want; supplies music; picks duration; picks mode (standard / music-video); picks effort level | D-006, D-010, D-013, D-018 |
| 3 | App computes max-permissible level + cost preview; user confirms | D-013, A-015 |
| 4 | Job runs async (user free to leave) | D-011, A-005 |
| 5 | Internal pipeline (the user never operates it): deterministic pre-filter → rich metadata extraction → narrative-arc judgment → render with music sync — all automatic behind the single submit | D-009, N-001, A-013 |
| 6 | Preview-and-approve UI shows the rendered Story Video, with **two clear actions: Approve (primary) and Refine (secondary)** | D-020 (publish-approval-always-on half), D-022 |
| 7 | (Optional) refine pass — user clicks "Refine this result" alongside Approve at the post-render moment; produces a new render and the same offer again. **Shipped**; since 2026-07-01 the request is open-ended natural language (one structured call → a re-rendered child snapshot, S-2.12.3), running as one synchronous HTTP call today | D-011, D-022, D-056 |
| 8 | User approves; app publishes to connected YouTube Studio account **(code complete; never executed — dry-run default; D-057 gate)** | D-007, D-020, A-003, D-057 |

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
| Media chronology (capture-time + GPS extraction) | **delivered 2026-06-11** | EXIF/filename/mtime reconciled with confidence; GPS read; judge ordered forward-in-time | A-021, N-014, D-043 |
| Rich-metadata enrichment (shot type, per-person expression, safety, specialness, obstructions) | **delivered 2026-06-11** | The planner can land emotional peaks, vary framing, drop blocked/explicit shots | A-022, D-043 |
| Cheap-first analysis hardening (thumbs to LLMs + time-bounded scene sampling) | **delivered 2026-06-11** | 1024px renditions feed every LLM call; long scenes subdivided | A-016, S-2.9.5, D-043 |
| Semantic near-duplicate suppression (best-of-burst) | **delivered 2026-06-11** | Embedding-similarity clustering, time-windowed, keeps the best retake | A-017, S-2.9.6, D-043 |
| Auto-derived trip cast + coverage-aware curation | **delivered 2026-06-11 (analysis half)** | Unique-face inventory, group-vs-crowd by recurrence breadth, coverage report; gemini default / insightface optional (D-044) | A-018, N-012, D-044 |
| Specialness-aware Stage 4 selection (4-term score + quality-floor rescue + specialness tie-breaks) | **delivered 2026-06-30** | The planner now uses the specialness signal it pays Tier-M to compute | S-2.10.2, ADR-0017, D-053 |
| Stage 5 judge: video share, intra-section variety, people / landscape + location balance, strict-forward opener | **delivered 2026-06-30** | Explicit MOTION / STILL candidates; no backwards-in-time opener; no stack of near-identical shots at the climax | S-2.10.3, ADR-0017, D-053 |
| Trip-cast group / crowd gate + cluster merge pass | **delivered 2026-07-01** (conjunctive appearance / day gate 2026-06-30; centroid merge pass 2026-07-01) | Detection-confidence bump and insightface default still open — S-2.10.4, restart Phase 2 | S-2.10.4, ADR-0020, D-044 |
| Named-destination coverage guarantee (brief intent → `ReservationSet` must-keep → judge coverage contract) | **delivered 2026-07-01** | A destination the brief names reaches the judge even when its shots score low; the same mechanism serves refinement's reserve / force-include | S-2.10.5, ADR-0017, D-056 |
| Capture-day stratified Stage 4 budget (replaces the global top-K) | **implemented 2026-07-01 — OFF** behind an A/B flag that no setting reaches (restart Phase 2 item) | Per-day allocation so the most-photographed place cannot starve the others | S-2.10.6, ADR-0020 |

### 3. Story Video generation

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Standard mode (background music under curated video) | mvp | The default Story Video mode | D-006, D-010 |
| Music-video sub-mode (full version) | mvp | User-supplied music drives sequencing; cuts beat-snap; section-to-media NL spec consumed by N-001 narrative judge | D-010, A-013, D-031, ADR-0012 |
| Section-to-media natural-language mapping | mvp | "Chorus → summit footage; bridge → rest stop" — passed verbatim to N-001 judge (reclassified from v1 → MVP, D-031) | A-013, D-031, ADR-0012 |
| User-chosen target duration | mvp | Per-job knob | D-014 |
| Music sourcing — user-supplied | mvp | User uploads or links audio file | D-018 |
| Snappier, fuller edits (photos 1–3 s, videos ≥ 2 s, every distinct location + time represented, per-viewpoint cap) | **delivered 2026-06-30** | ~40–60 clips per 120 s; verified on a reconstruction render (44 clips / 115 s) | S-2.11.1, D-054 |
| Burst-montage clip type | **delivered 2026-06-30** | A dense same-backdrop burst becomes a rapid 2–4 s montage instead of six held photos | S-2.11.4, D-054 |
| Opt-in AI title / splash card + AI-written title text | **delivered 2026-06-30** | Remote image-gen background (gemini-2.5-flash-image) with the main people composited; a cheap Tier-S call writes a 2–5 word title from the brief, heuristic fallback; refinable in plain language since 2026-07-01 | S-2.11.5, S-2.11.7, S-2.12.4, D-054, D-055 |
| Music mood / tempo / section matching (standard mode too, not only music-video mode) | **delivered 2026-06-30** | Per-section mood (calm / moderate / energetic) informs the judge and the pacing; librosa-only analysis | S-2.11.6, ADR-0012 |
| `PlanDirective` positional / tempo / soft-align pacing levers | **delivered 2026-07-01** | One shaping contract that Stage 6 consumes and that both initial planning and refinement emit | S-2.12.1, S-2.12.2, ADR-0019, D-056 |
| Music sourcing — royalty-free starter pack | v1 | Curated catalog ships in-app | D-018 |
| Music sourcing — licensed library integration | v1 | Third-party (e.g., Epidemic-Sound-class) integration | D-018 |
| Music sourcing — generated music | v2 | Suno-style; cost + quality bounds need work | D-018 |

### 4. Effort-level UX & cost surfacing

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Effort levels L1–L3 with max-permissible recommendation | mvp — picker + cost preview shipped; the selected level does not yet change pipeline behaviour (restart audit 2026-10-24; S-2.9.18) | Translates user intent + config into actionable level | D-013, A-015, N-006 |
| Effort levels L4–L5 | v1 | Higher-scale envelopes | D-013, A-015 |
| Cost-transparency UI | v1 — the metering underneath is token-accurate from real provider usage since 2026-06-17 (D-048); the running-spend UI remains v1 | Running spend by provider / job / operation | A-004, A-015, D-048 |
| Upgrade-path agent | v1 | Agentic explanation of what config change unlocks higher levels | A-015, N-006 |
| Per-day spend cap (hard stop) | mvp-lite — pre-job total-cap and per-provider-cap check shipped; no mid-job guard yet (S-3.11.1, restart Phase 2) | Backstop against runaway jobs | A-004 |

### 5. Preview, approve, publish

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Preview-and-approve UI (always on, no opt-out) | mvp | Foundational trust gate; surfaces Approve + Refine as twin actions | D-020 (publish-approval half), D-022 |
| Refine loop (offered post-render, alongside Approve) | mvp — **delivered**; open-ended natural-language request → re-rendered child snapshot since 2026-07-01 | Optional second-place action on the result; not a job-creation toggle. Today one synchronous HTTP call — refine-as-a-job + publish from any snapshot is S-3.5.5 | D-011, D-022, S-2.12.3, D-056 |
| In-app per-phase diagnostics + decision-level feedback ("Inspect & give feedback": correct / incorrect / should-be-different + note + page screenshot), picked up out-of-band by Claude | **delivered 2026-06-14** | Stage 4 keep / drop reasons, Stage 5 selection, Stage 6 clips, trip cast; the SQLite `feedback` table is authoritative, the JSONL file an append-only submission log | A-023, D-045, D-046, N-015 |
| Job- and phase-level feedback | **delivered 2026-06-30** | Feedback on the whole video or on one phase, not only on a single media decision | S-2.11.2 |
| Richer live module / decision progress view | **delivered 2026-06-30** | Each stage expands into its sub-module chips while the job runs — not just "Step N of 7" | S-2.11.3 |
| Multi-version artifact comparison | v1 | Side-by-side after refine; natural home for comparing original vs. refined renders | A-006, N-003 |
| Publish to YouTube via connected Studio account | mvp — code complete 2026-05-05 (PR #19); **never executed** (dry-run default `IC_PUBLISH_DRY_RUN=1`, env-var credentials, in-app OAuth not built); the one open MVP gate (D-057) | The single MVP platform; Connect-in-Settings is S-3.3.5 | D-007, D-057, ADR-0013 |
| Publishing audit log | mvp — writer shipped; the table is empty because no publish has run | Append-only record per project | A-003 |
| Multi-platform publish (Instagram, Facebook, X) | Instagram + Facebook: **code delivered 2026-05-11** (env-var credentials, dry-run default, never live-tested); X remains v1 (S-3.3.4) | Instagram Reels: container → poll → publish, needs a public HTTPS media URL; Facebook Page video; one platform per publish | D-007, ADR-0013, E-3.3 |
| Per-platform formatting (aspect ratio, duration) | v1 — output is 16:9 1080p only today (S-3.3.3) | Co-arrives with multi-platform | D-007 |

### 6. Internal model routing & execution

These are internal mechanisms that make the single click faster and cheaper — they never surface as a control plane the user operates. The user just describes the outputs they want; the AI decides how to route and execute.

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Remote-first routing default | mvp | Required to hit 2–5 hr ceiling at MVP scale | D-009, D-012, D-016 |
| Routing abstraction in place from day one | mvp | Local-first config flip in v1, not rewrite | D-016 |
| Single orchestrator with structured tool calls | mvp — shipped instead as a deterministic 9-stage runner with single-shot structured LLM calls; no tool-call orchestrator was built (ADR amendment pending in S-2.13.5) | Hosts the agentic UX surface | D-017 |
| Operation-aware LLM router | v1 | Per-sub-operation routing; gates local-first v1 | E-3.1, D-016, N-002 |
| Local-first routing default | v1 — **no on-device runtime exists yet** (E-3.1, restart Phase 5) | Config flip + N-002 router | E-3.1, D-016 |
| Multi-agent harness (planner + media-analyst + editor + publisher) | v2 | Co-arrives with conversational refinement at scale | E-4.2, D-017 |

> The single-orchestrator and multi-agent-harness rows describe **internal implementation detail**, not anything the user configures. However the AI is wired internally, the user still just describes the outputs they want in natural language and approves the result.

> **2026-10-25:** there is no on-device model routing today — no local LLM runtime exists, the local image-embedder interface (ADR-0018) has zero callers, and every AI call goes to Anthropic or Google per `config/llm-routing.yaml` (claude-sonnet-4-6 for Tier-M operations, claude-opus-4-8 as the judge, gemini-2.5-flash for Tier-S, gemini-2.5-flash-image for the title-card background, gemini-embedding-001 for embeddings). Local-first is E-3.1, restart Phase 5.

### 7. Privacy, security, accessibility

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Privacy posture for faces and locations (consent / strip-EXIF / blur-faces) | mvp — **designed; transforms built as a library, not enforced (S-3.1.4)** | Required because remote-first sends images off-device. Today: `strip_exif` / `blur_faces` exist with zero call sites; Settings shows read-only hard-coded text; what leaves the machine is a re-encoded 1024 px rendition (the original is only the silent fallback when a rendition is missing), sent unmodified. Explicit EXIF strip + truthful "what we send" copy is restart Phase 2 (S-3.1.4); the full per-project toggle matrix is Phase 5 (S-3.1.3) | A-002, D-016, ADR-0016, S-3.1.4 |
| Auto-generated captions | mvp-lite — not built (no caption code; S-3.3.7) | At curation time, user reviews pre-publish | A-009, D-007 |
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
| AI crowd removal (inpaint non-group people) | v2 — E-4.6 (created 2026-10-24 from S-2.9.7; remote default / local optional per D-044; parked behind the Trip Package gate) | Generative fill over A-018 cast masks; opt-in per photo in refine | E-4.6, A-019, N-012, D-044, ADR-0016 |

### 11. Conversational refinement & agentic editing dialogue

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Natural-language refine ("more landscape, less faces") | **delivered 2026-07-01** (single-request open-ended refinement; multi-turn chat remains v2) | One structured call maps a free request onto a directive patch / reserved destinations / brief addendum / title-card patch and re-renders a child snapshot — pacing-only requests re-run Stage 6 alone, content requests re-judge; no on-demand media re-analysis yet | S-2.12.3, ADR-0019, D-056, E-4.3 |
| Title-card refinement in plain language (text / background image / placement / appearance) | **delivered 2026-07-01** | The card is re-injected on every refine | S-2.12.4 |
| Conversational style adjustments via chat | v2 | "Make this feel more cinematic" | E-4.3, A-014 |

### 12. Mobile

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Mobile UI + camera-roll watcher | v2 | Own epic; first mobile touchpoint is A-012 in v1 | D-019, A-012 |

### 13. Hosted-service mode

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Hosted multi-tenant deployment | v3 | Per CLAUDE.md mission; config flip on the self-hosted-first design | (CLAUDE.md) |

### 14. Trip Package — autonomous multi-artifact creation (the north star)

| Feature | Phase | One-line | Linked |
|---|---|---|---|
| Trip segmentation (time + GPS + content clustering into events/locations/themes) | v2 | Ingest-side EXIF GPS parsing landed 2026-06-11 with the chronology work (D-043); the segmentation itself is v2 | A-020, N-013, D-043 |
| Density-driven artifact allocation | v2 | Rich clusters earn dedicated videos; thin clusters merge; standouts become reels | A-020, N-013, D-042 |
| Package plan → N artifact briefs executed by the single-video pipeline | v2 | One shared analysis pass via the content-addressed cache; cost paid once | A-020, N-007 |
| Package preview + per-artifact approve/refine/publish | v2 | One approval surface for the whole portfolio | A-020, D-020 |
| Overall trip video + montage as standing package members | v2 | Every cluster contributes weighted material | A-020 |

> **Sequencing gate (D-042, user-stated):** no package code before single-video quality is mastered — A-016/A-017 and the v1 quality milestones come first. Deterministic seeds may pilot inside v1.2's multi-output orchestration. **2026-10-25:** A-016/A-017 were delivered on 2026-06-11; the quality gate itself (its measurable definition — the decision D-057 reserves as D-058, not yet written — in restart Phase 2; its run in Phase 3) is still ahead, and the package pilot is restart Phase 6 (E-4.5), opened only by a gate-met decision.

---

## Project as a versioned artifact (cross-cutting)

N-003 reframes the entire project / job storage layer as a content-addressed DAG of snapshots. This is **not its own theme** — it is a substrate that makes A-006 (multi-version comparison), A-003 (publishing audit log), and A-012 (live-job multi-output orchestration) cleaner. Phase: aligned with whichever consumer feature lands first; concrete schema goes through E-1.3.

---

## Out of MVP scope (explicit)

To keep the MVP honest, the following are **explicitly NOT in MVP** even though they appear in this catalog:

- Multiple artifact types in one job (only Story Video in MVP — D-006).
- Multiple platforms in one publish (only YouTube in MVP — D-007). *2026-10-25:* Instagram and Facebook connector *code* nevertheless landed on 2026-05-11 (dry-run only, never live-tested); the publish modal still offers one platform per publish.
- Live-job pattern (v1 — A-012). *2026-10-25:* restart Phase 6, behind the D-042 gate (D-057).
- Reference-media style learning (v1 — A-014).
- Local-first LLM routing default (v1 — D-016). *2026-10-25:* no on-device runtime exists yet; restart Phase 5 (D-057).
- Auto photo / video editing (v1).
- Mobile UI (v2 — D-019).
- Multi-agent harness (v2 — D-017). *2026-10-25:* the MVP has no tool-call orchestrator to refactor — it is a deterministic 9-stage runner with single-shot structured calls.
- Conversational refinement at scale (v2). *2026-10-25:* single-request open-ended NL refinement shipped 2026-07-01; the multi-turn chat remains v2.

Anything that doesn't appear in the MVP rows above is automatically v1+ unless the team explicitly promotes it during E-1.4 roadmap grooming.

---

## Pending (round 2 of E-1.2, if needed; otherwise carries to E-1.4)

- [ ] Tech-stack-independent acceptance tests for each MVP-tagged feature row above (E-1.3 will tie these to chosen tech).
- [ ] First-pass effort estimate per MVP feature (E-1.4 will turn into a concrete schedule).
- [ ] Per-feature owner / story decomposition (created on-demand by `work-tracker` as work begins).
