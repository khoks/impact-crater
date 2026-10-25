# Impact Crater — Landscape and restart plan (2026-10-24)

> Produced by a Claude Code session on 2026-10-24 after a ~4-month pause (last commit `da34766`, 2026-07-01). Method: repo + tracker + docs + local app-state scouting, then an 8-dimension audit workflow (tracker, hygiene, code-vs-claims, vision/future, decisions, testing, usability, done-inventory), each dimension adversarially verified by a skeptic agent, then a 3-angle planning panel, a judge synthesis and a completeness critic. Every claim below cites a file or a tracker item. This is an internal working document; `docs/OVERVIEW.md` stays the external, ID-free mirror.

---

## 0. Verdict in one screen

**Usable today, for the owner, as a local "make and refine one Story Video" tool. Not yet usable as the 1-click-and-publish product for anyone else.**

- The app boots cleanly today (probed on port 8766): migrations run, the built SPA serves, all 14 API routers answer, both API keys are present (encrypted), the $100 daily cap is set, and 31 projects / 24 successful snapshots play inline.
- The whole single-video journey works end to end and was proven on a real 1,663-asset trip (D-014 passed 2026-06-18, 2h55m wall-clock) and re-verified live on 2026-07-01: folder scan → brief → audio → duration/mode → effort & cost → async job with live progress → inline preview → plain-language refine → inspect & feedback.
- What does **not** work for a user: publishing (dry-run default, env-var credentials only, in-app OAuth never built, zero publishes ever executed); the cross-project profile (backend only, never exercised); the person library (never influences curation); privacy toggles (hard-coded text, transforms never invoked); restart survival of live jobs (in-memory registry); any multi-output or reel-shaped artifact (16:9 only); mobile.
- The biggest risk before the next paid run is model drift: routing pins `claude-sonnet-4-6` / `claude-opus-4-8` (and `gemini-2.5-flash` / `gemini-2.5-flash-image` / `gemini-embedding-001`) with the IDs baked into prompt filenames, rate cards, the temperature guard and a test. Re-runs over already-analysed media would survive on cache hits, but any new media or changed brief would fail at Stage 3 with an unmapped raw error, after the Gemini spend for Stage 2 has already been incurred, and the fail-soft brief parse would silently degrade and drop the destination reservations (the Vegas fix). Nothing pings the providers before a job starts; the wizard's key test is still a stub.
- The MVP gate is honestly half-met: curation + render + preview passed on real media (cold-equivalent ≈ 4 h, about $50 of API spend for the dataset); the "publish to the connected YouTube account" half of D-014 and 9 of the 10 `MVP.md` pre-flight boxes have never been exercised. No full-scale run has happened since the E-2.10/E-2.11/E-2.12 quality fixes, so their acceptance criteria are verified only on 55-media tests.
- Operational debt is real: 92 GB of per-project scene caches with no cleanup, a 47 MB telemetry file scanned per job, an in-memory job registry that silently lost three large jobs on a restart, and no CI.
- Two things to know before exposing it beyond your own machine: the local API and WebSocket have no authentication or origin check (safe on loopback, unsafe behind `--host 0.0.0.0` or the public tunnel Instagram publishing needs), and there is no way to delete a project's derived data (LLM payloads, scene frames, feedback screenshots) from the app.

---

## 1. Where things stand

| Fact | Value |
|---|---|
| Last build session | 2026-06-29 → 2026-07-01 (E-2.10, E-2.11, E-2.12 shipped; PRs #67–#74) |
| Last commit | `da34766` 2026-07-01 — title-card glyph fix (S-2.11.7) |
| Days idle | ~115 |
| Branch state | `master` clean; untracked `.claude/launch.json`, `.scratch/`; stale detached worktree `.claude/worktrees/trusting-rhodes-bb0b37` (no unmerged work) |
| Backend tests (run today) | 476 passed, 7 skipped (integration suite needs `--integration` + real keys) |
| Frontend (run today) | `tsc` clean; 38 vitest passed across 10 files |
| Tracker | 5 initiatives, 34 epics, 113 stories, 30 tasks; BOARD last updated 2026-07-01 |
| Local app state | 31 projects (13 never produced a snapshot), 24 snapshots (22 rendered MP4s, 2 stuck `pending` from interrupted 2026-06-30 runs) under `~/.impact-crater/projects`; 1,651 media rows; LLM cache 101 MB / 13,338 entries; `telemetry.jsonl` 47 MB / 103,746 lines; `audit.jsonl` absent and `audit` table empty; `connector_credentials` empty; `profile/` dir empty (created only by today's probe) |
| MVP gate (D-014) | PASSED 2026-06-18 on a real 1,663-asset trip (1,481 photos + 182 videos → 2,067 shots → 108 s video, confidence 0.85). The cold attempt on 2026-06-17 ran 2h55m and died at the judge on Anthropic credit exhaustion (which exposed the 5× metering bug, D-048); the validated run on 2026-06-18 was a cache-warm resume (94 % cache hits): ~60 min curation + 9 min render for $18.84. Cold-equivalent ≈ 4 h (inside the 2–5 h ceiling but near the top) and true spend for the dataset ≈ $50+. A fully cached re-run still takes ~31 min of deterministic work. None of these figures is recorded in BOARD or the decisions log. Publish step never executed |
| Scale runs since the quality fixes | None. The last ≥ 900-media jobs started 2026-06-29 local, before PR #72 landed the Vegas fix; every project since has 55 media (title-card tests). Three of those 2026-06-30 large jobs have a `started` event and no `completed`/`failed` event: lost on a server restart, invisible to any audit |
| Model IDs exercised at scale | The models that produced every validated output were `claude-sonnet-4-5` / `claude-opus-4-5`; the current pins (`4-6` / `4-8`) have ~85 real calls behind them on two 55-asset tests, and the integrity test now bans the 4-5 IDs |
| Disk | `~/.impact-crater/projects` is **92 GB**; six projects weigh 8–14 GB each because scene frames and thumbnails are cached per project (`stage1_ingest.py:274`), so each re-run of the same trip duplicates ~13 GB. The shared LLM cache is 101 MB. No cleanup, sharing or disk accounting exists |
| Pending in-app feedback | 11 items still `new` (ids 1–3 and 5–12; id 3 is a Claude test entry) although E-2.10/E-2.11 addressed most |
| Installed optional backends | `insightface`, `torch`, `onnxruntime`, `open_clip`, `reverse_geocoder`: none installed; every run so far used the defaults (Gemini cast embedder, caption-then-embed, text-only destination matching) |
| Public docs site | live at khoks.github.io/impact-crater (OVERVIEW only) |

---

## 2. What is done

### 2.1 Macro — what a user can do today

- Install locally (Python 3.12 venv + built React bundle) and run `impact-crater`, which starts FastAPI on localhost and opens the browser. First run shows a 6-step setup wizard (keys, caps, storage).
- Dashboard with persisted projects, snapshots, render-status badges, inline MP4 playback, and links to Inspect, People, Feedback, Workplan, Settings.
- New project: name, brief in plain words, folder path (server-side scan), audio file, target duration, standard or music-video mode, section-to-media NL spec, optional AI title card.
- Mandatory Effort & cost page: L1–L3 envelopes, recommended level, per-tier cost preview, fits-today-budget gate.
- Live job view over WebSocket: 7 plain-language stages with sub-module chips, live spend, cancel, and a streaming "Decisions so far" diagnostics panel.
- Preview page: HTML5 playback; free-text Refine that re-renders a child snapshot; Approve & publish modal (YouTube / Instagram / Facebook picker, title, description, visibility, dry-run badge, audit token); Inspect & give feedback.
- Inspect page keyed by snapshot (survives server restarts): per-phase decision cards with thumbnails; feedback at decision, phase and job level with a whole-page screenshot.
- Settings (keys never echoed, spend caps, privacy posture shown read-only), Person library (add people + up to 5 face photos), Feedback tracker, Workplan tracker (reads `project/`, edits priority overrides).
- Output: 1920×1080/30fps H.264 Story Video, standard and music-video modes, optional AI title card, burst-montage clips, two-pass loudness-normalised music with fade, faststart mux.
- Publishing: three connectors (YouTube, Instagram Reels, Facebook Page) behind env-var credentials with a dry-run default and an append-only audit log — code complete, never exercised.

### 2.2 Medium — subsystems

| Area | What exists | Where |
|---|---|---|
| API | 14 routers, 47 routes + health + SPA fallback (setup, settings, projects, jobs incl. WS, folder scan, effort, snapshots, media thumbs, feedback, workplan, persons, publish, profile) | `backend/impact_crater/api/` |
| Pipeline | 13 steps: Stage 0 music, 0.5 brief intent, 1 ingest, 2 bulk ops, 3 rich metadata, 3.5 trip cast, 4 pre-filter (1,180 lines), 5 narrative judge, 6 plan, 6.5 second-guess, 6.x title card, 7 render, 9 agentic refine | `backend/impact_crater/pipeline/` |
| LLM layer | `LLMClient` protocol; Anthropic + Google clients; `LLMRouter` with 9 public ops; content-addressed cache; sha256-versioned prompts; 15 routed ops in `config/llm-routing.yaml`; 7 Jinja2 prompts | `backend/impact_crater/llm_clients/`, `prompts/`, `config/` |
| Media | ffmpeg resolver + async subprocess; librosa music analyser (beats, sections, moods, cut grid); capture-time + GPS reconciliation; privacy transforms (library only); face detect (mediapipe → OpenCV Haar fallback); cast clustering; face embeddings (gemini default, insightface optional); N-008 collage builder; pluggable image embedder (local CLIP stub) | `backend/impact_crater/media/` |
| Connectors | `Connector` protocol + error hierarchy; `DryRunConnector`; YouTube (env-var path), Instagram (container → poll → publish), Facebook (Page video) | `backend/impact_crater/connectors/` |
| Jobs / workers | In-process `JobRegistry` state machine with WS fan-out and late-joiner replay; 3-class worker pool (cpu / ffmpeg / network) | `backend/impact_crater/jobs/`, `workers/` |
| Storage | aiosqlite WAL; 6 idempotent SQL migrations; 14 tables (settings, projects, media, project_media, snapshots, audit, cache_index, connector_credentials, quota_state, persons, person_face_photos, feedback, workplan_overrides, schema_migrations) | `backend/impact_crater/storage/` |
| Cross-cutting | Token-accurate telemetry (5 event types) + `JobCostSummary`; dual-cap quota; 6 rate cards; Fernet secrets; audit JSONL + SQLite mirror; deterministic cross-project profile (backend only) | `telemetry.py`, `quota.py`, `rate_cards.py`, `crypto.py`, `audit.py`, `profile.py` |
| Frontend | 11 routes, Zustand stores, typed API modules, 10 test files | `frontend/src/` |
| Tooling | `impact-crater` CLI; Windows `start.ps1` / `dev.ps1` / `bootstrap.ps1` (mac/linux stubs); `scripts/feedback.py`; Stop-hook housekeeping skills; GitHub Pages workflow | `scripts/`, `.claude/`, `.github/` |

### 2.3 Micro — notable mechanisms present in code

- Content-addressed LLM cache keyed on content hash + provider + model + model version + operation + prompt version + canonical params, with the key embedded in payload filenames (D-040) and purge-by-migration.
- Three-source capture-time reconciliation with confidence (EXIF 1.0 → filename pattern 0.8 → mtime 0.4) plus EXIF GPS parsing (N-014).
- Rich metadata schema: shot type, main subjects with expression and prominence, scenery, camera-quality notes, specialness, safety level, obstruction level (A-022).
- Cheap-first analysis: 256px + 1024px renditions; long video scenes subdivided; 3 frames per scene (A-016).
- Best-of-burst semantic dedup (cosine ≥ 0.93 inside a 120 s window, keep the most special member) (A-017).
- Trip cast: detect → crop → embed → greedy cluster → conjunctive group gate (appearances ≥ 3, days ≥ 2, breadth ≥ 3) → merge pass at centroid cosine ≥ 0.92 → coverage report (N-012, ADR-0020).
- Specialness-aware Stage 4: 4-term score (quality 0.25, narrative 0.40, specialness 0.20, diversity 0.15), quality-floor rescue at specialness ≥ 0.75, safety floor, min-video floor, pHash + semantic dedup, location/time clustering caps, per-viewpoint GPS cap, filter log of every drop (ADR-0017).
- `ReservationSet` / named-destination coverage: brief parse → destination mapping (text + offline reverse-geocode) → reserve top 2 per destination (≤ ~25 % of target) → judge HARD coverage block; shared by refinement and feedback (S-2.10.5).
- `PlanDirective`: duration bands, positional rules, tempo bands, soft section-align, deep-merge, fixed application order in Stage 6, persisted on the plan (ADR-0019).
- Capture-day stratified budget, implemented but OFF behind an A/B flag (ADR-0020).
- MOTION/STILL candidate tags and a judge prompt enforcing ≥ 25 % motion share, variety caps, people/landscape balance, per-viewpoint cap, chronological opener (S-2.10.3).
- Snappy per-clip duration band (photos 1–3 s, video ≥ 2 s) and ≤ 3 clips per location (S-2.11.1, T-2.11.1.6).
- Burst-montage clip type: dense same-backdrop bursts collapse to one 2–4 s sequence (S-2.11.4).
- Music mood/section matching in both modes; cut grid snapping to beats and section boundaries (S-2.11.6, D-041).
- AI title card: Tier-S title text with heuristic fallback, remote image background (faces never sent), PIL composite with cast faces, shrink-to-fit, glyph folding; refinable in plain language and re-injected on every refine (S-2.11.5, S-2.11.7, S-2.12.4).
- Agentic refinement: one richly-contextualised structured call → `RefinementOutcome` (directive patch / reservations / brief addendum / title-card patch / explanation); light edits re-run Stage 6 only; content edits reconstruct Stage 2/3 from sidecars + cache and re-judge; renders a child snapshot (S-2.12.3).
- Second-guess pass with auto-apply above 0.85 confidence, persisted `second_guess.json` (M6).
- Token-accurate metering from real provider usage (D-048); pessimistic dual-cap quota pre-flight (D-034); effort levels L1–L3 with budget fit.
- Decision-level feedback with page screenshots, phase- and job-level feedback, feedback and workplan tracker pages, workplan priority overrides table (N-015, A-023, A-024).
- Dry-run connector wrapper that still runs real validation; Fernet-encrypted credential rows; audit JSONL authoritative with SQLite mirror.

---

## 3. The honest MVP gaps (claimed done vs what runs)

Every row below was confirmed against the code by at least two independent audit agents and a skeptic verifier on 2026-10-24.

| Claimed (epic marked done) | Reality in code | Evidence |
|---|---|---|
| M7 YouTube publish: OAuth loopback + real upload (E-2.8) | In-app OAuth init/callback never finished; credentials via env vars + manual mint script; publish defaults to dry-run; no publish of any kind ever executed | `connectors/youtube.py:5-16,203`, `connectors/dry_run.py:102-110`, `docs/connectors/youtube-setup.md`, empty `~/.impact-crater/audit.jsonl` |
| M5 privacy panel: three toggles + strip-EXIF + face-blur in the pipeline (E-2.6) | Transforms exist as a library only; zero call sites in `api/`, `pipeline/`, `jobs/`; Settings panel shows hard-coded read-only defaults; images go to remote LLMs unmodified | `media/privacy.py`, `frontend/src/routes/Settings.tsx:1-3`, grep of call sites |
| M5 N-008 recognition in Stage 3 (E-2.6) | Collage builder exists; never passed to Stage 3; `recognized_persons` always empty; S-2.6.2 deferred to v1 yet its acceptance boxes are all ticked | `media/collage.py`, `pipeline/stage3_metadata.py:7-11`, `project/stories/S-2.6.2-*.md` |
| M8 cross-project profile with suggestions + reset UI (E-2.9) | Backend + 4 endpoints exist; zero frontend references; no event emitter anywhere; profile has never been derived (no `profile/` dir) | `profile.py`, `api/profile.py`, grep of `frontend/src` |
| M6 second-guess Apply/Skip/Modify UI (E-2.7) | Overrides auto-apply above 0.85; nothing surfaced in the UI | `pipeline/stage6_plan.py:833-845`, grep of `frontend/src` |
| MVP constraint #16 auto-captions (A-009) | No subtitle/caption code at all; no tracker item | `docs/roadmap/MVP.md` #16 |
| MVP constraint #4 resumable jobs | Job registry is in-memory; live/preview views 404 after restart; finished jobs reviewable via the snapshot-keyed Inspect workaround only | `jobs/registry.py`, S-2.9.19 (backlog) |
| ADR-0014 single `Orchestrator` tool-call loop | Never built; pipeline is a deterministic runner with discrete structured LLM calls; 4 routed Tier-M ops have no caller or prompt | grep `class Orchestrator`, `config/llm-routing.yaml:89-112` |
| ADR-0012 Madmom beat detection | librosa-only (Madmom does not build on Python 3.12); ADR and MVP.md #8 not amended | `pyproject.toml:45-50`, `media/music.py:3-13` |
| ADR-0010 dlib / pyexiv2 / rawpy / smartcrop | mediapipe (dead on 0.10.35 → OpenCV Haar), piexif, no rawpy (folder scan still advertises RAW), centre-crop instead of saliency crop | `media/_face_detect.py:3-8`, `api/folder.py:3`, `stage7_render.py:358-364` |
| Routing to current models | Pinned to `claude-sonnet-4-6` / `claude-opus-4-8` / `gemini-2.5-flash`; the Claude 5 family is now current, so Tier-M/L calls may fail at runtime; temperature guard and integrity test hard-code the 4.x IDs; no rate card for `gemini-2.5-flash-image` | `config/llm-routing.yaml:73,126`, `anthropic_client.py:32-38`, `tests/test_routing_config_integrity.py:34-41` |
| Reel-shaped output for Instagram | Output aspect hard-coded 16:9; portrait video letterboxed | `pipeline/stage6_plan.py:154,524` |
| Effort levels L1–L3 drive the pipeline (D-013) | The selected level never reaches the submit request; it only changes the cost preview. The pipeline runs identically at every level | `api/jobs.py:280-290`, `frontend/src/routes/EffortAndCost.tsx` |
| Refine loop bounded, cancellable, resumable (E-2.7 ACs) | One synchronous HTTP call that re-judges and re-renders inline (2m11s on a small project) with no quota pre-check, progress or cancel; the child snapshot can be inspected but not published or refined again from the UI | `api/snapshots.py:161-199`, `frontend/src/routes/SnapshotInspect.tsx` |
| Stratified budget and local embedder switchable (ADR-0018/0020) | No settings key or env flag reaches the runner for either; `build_image_embedder` has zero callers, so both ship inert | `pipeline/stage4_prefilter.py:88-92`, `media/image_embed.py:43-61` |
| S-2.10.4 cast tightening fully landed | Merge pass landed; detection-confidence bump (0.5 → 0.6) and insightface default did not. PR #72 flipped S-2.10.4/5/6/7 to done by changing only the status line; S-2.10.7's "full-job smoke run on the new models" box is unchecked, so the model bump was never smoke-tested end to end | `media/_face_detect.py:53`, `storage/settings.py:27`, `git show 2bf66b1` |
| S-2.9.17 "add faststart" | Premise is false: `-movflags +faststart` has been in the final mux since 2026-05-04; the inline-preview stall needs a different root cause | `pipeline/stage7_render.py:524` |
| Setup wizard key test | Still the M0 stub: any non-empty string passes; keys are only validated when a job runs | `api/setup.py:80-98` |
| Approve button copy | Says "Approve uploads this MP4 to your connected YouTube account" while dry-run is the default and no account is connected | `frontend/src/routes/JobPreview.tsx:207` |
| S-2.10.5 offline reverse-geocoding of GPS to destinations | `reverse_geocoder` is neither declared in `pyproject.toml` nor installed; the import is wrapped in a fail-soft `try`, so destination mapping has only ever matched on text | `pipeline/destinations.py:147-153` |
| M6 second-guess is "AI-offered, user-accepted" | Overrides above 0.85 confidence would be applied silently, but every one of the 13 `second_guess.json` files on disk has confidence 0.72–0.75, so the branch has never fired, nothing has ever been shown to the user, and several files contain only shorten/lengthen overrides the applier cannot handle. The per-job Tier-M call has had zero product effect | `pipeline/runner.py:548-562`, `pipeline/stage6_plan.py:857-862` |
| Spend caps enforced "pre-job and per-stage" (quota docstring) | One pre-job check only (`runner.py:178`); no mid-job guard; refinement, title-card generation and any direct router use run uncapped. Anthropic is ~99 % of spend | `quota.py:6`, `llm_clients/router.py:661-669` |
| Refine child snapshots are first-class | Children hold only `plan.json` + `render.mp4`; no `cost_summary.json` or `diagnostics.json`, so refinement cost is unpersisted and the Inspect page shows a misleading "predates the feature" message | `pipeline/stage9_refine.py`, `api/snapshots.py:78-83` |
| Routing config matches the router | 6 of 15 routed ops have no router method, prompt or caller (`caption_video_scene`, `extract_metadata_video_scene`, `recommend_effort_level`, `explain_cost`, `explain_upgrade_path`, `orchestrator_reasoning`); the designed `analyze_music_duration_mismatch` was never built either | `config/llm-routing.yaml`, `llm_clients/router.py` |
| N-008 / N-011 cache dimensions | `library_version_hash` and `privacy_class` are NULL on 100 % of 13,338 cache rows | `cache_index` table |
| ADR-0013 credential model | The OAuth + Fernet-in-SQLite path is dormant, not removed: `connector_credentials` is still read, nothing writes it. The shipped model is plaintext env vars layered beside it; no ADR amendment or D-NNN records that. `docs/OVERVIEW.md` still promises "secure, encrypted credential storage and a full publishing audit trail" | `connectors/youtube.py:13-16`, `api/publish.py:243`, `docs/OVERVIEW.md:354-355` |
| Feedback JSONL is a "mirror" | Append-only on POST with no delete endpoint; ids 4 and 13 were deleted from the DB out of band, so the two stores have diverged | `api/feedback.py` |
| Render honours the plan's output size | `RenderPlan.output_width/height/aspect` are dead fields; Stage 7 uses module constants 1920×1080, so any 9:16 work must first make the renderer read the plan | `pipeline/stage7_render.py:78-79` |
| Cost fallback "uses the rate card when usage is absent" | `_ballpark_cost` loads the card and then ignores it, always returning the per-tier placeholder (affects embeddings and the title-card image, which has no card at all) | `llm_clients/router.py:765-777` |

---

## 4. Pending landscape

### 4.1 Features pending (tracked)

**Open MVP-era items (the only ones with groomed bodies):**

| ID | Title | Status | Priority | Phase | Note |
|---|---|---|---|---|---|
| I-2 | MVP — Story Video to YouTube | in-progress | P0 | mvp | Cannot close honestly: publish half of D-014 never executed; `MVP.md` pre-flight all unticked; Children list is a 2026-05-05 fossil |
| E-2.9 | Cross-project profile + polish + D-014 validation | in-progress | P0 | mvp | Profile UI unwired; RAW decode, path-move recovery, cross-OS verification unmet; Children lists 6 of 20 stories |
| E-2.10 | Feedback-driven curation quality | in-progress (frontmatter) / done (BOARD) | P0 | mvp | All 8 stories shipped; ACs unverified (no post-fix full SW-US re-run recorded) |
| S-2.10.8 | Local CLIP/SigLIP embedder | in-progress | P1 | v1 | Interface + stub only; weights/GPU decision pending; ADR-0018 still proposed; idle 4 months |
| S-2.9.18 | Token-aware pre-job cost estimate | todo | P2 | mvp-hardening | Small; 47 MB of real telemetry available to calibrate from |
| S-2.9.17 | Faststart render | todo | P3 | mvp-hardening | Premise false: all 22 renders on disk already have `moov` before `mdat`; the real stall (Content-Disposition `attachment`) was fixed in PR #40 eight days before the story was filed. Close as invalid |
| S-2.9.19 | Persist job registry across restarts (A-025) | backlog | P2 | v1 | Breaks MVP constraint #4; recommended promotion to mvp-hardening P1 |
| S-2.9.15 | Two-phase pre-filter (D-049) | backlog | P2 | v1 | Saves ~½ of Tier-M spend; mis-parented to I-3; needs a validation run |
| S-2.9.4 | Crossfades on slow tempo | todo | P3 | v1 | `TransitionType` has crossfade but no xfade filter |
| S-2.9.7 | AI crowd removal (A-019) | ready | P3 | v2 | Blocked on a provider decision; "ready" is not a defined status |
| S-2.6.2 | N-008 collage → Stage 3 | deferred | P0 | v1 | All AC boxes ticked but code absent; likely superseded by A-018 cast |
| S-2.6.4 | N-011 privacy routing schema | deferred | P0 | v1 | Same false-tick problem; duplicates S-3.1.3 |

**Future-phase shells (I-3 / I-4 / I-5):** 17 epics and 35 stories (23 v1, 9 v2, 3 v3) backfilled on 2026-06-14 whose bodies are one-line placeholders whose single acceptance box equals the title ("groom into tasks when v1 opens"); every child reference uses the wrong `E-x.y.z` prefix. Their content is summarised by phase in §4.5. Two of them are already partially shipped: E-3.3 (Instagram + Facebook connectors landed 2026-05-11 in PR #34, a month before the epic was created; X connector and 9:16 formatting remain) and S-3.7.2 (E-2.12 already covers tempo/section pacing requests).

**Inline tasks that were never filed:** 35 distinct `T-2.10.x` / `T-2.11.1.x` task IDs are referenced inside stories but exist only as bullets; `project/tasks/` holds only the 30 done `T-1.x` files.

### 4.2 Improvements / hardening pending (code-verified, mostly untracked)

Publish and trust
- Finish in-app YouTube OAuth (loopback callback → `connector_credentials`, which already has encrypt/decrypt helpers) plus Settings Connect/Disconnect and an audit-log viewer, or ratify env-var credentials in an ADR and change the UI copy.
- Derive the Approve caption and default title from connector status and the title card; run one dry-run publish per platform to prove the audit path.
- Instagram live posting needs a public HTTPS URL for the MP4 (`IC_PUBLIC_BASE_URL`), awkward for a self-hosted desktop app; needs a tunnel or upload-host story.
- Wire the privacy posture: real settings keys, three toggles, `prepare_for_llm` at the rendition-creation point; or state plainly what is sent (re-encoded 1024px renditions without EXIF, faces not blurred).
- Rewrite Settings/Setup privacy copy that leaks "LLM", "ADR-0016", "E-2.6", "recognized_persons=[]"; rename diagnostics labels ("Pre-filter", "Narrative judge", "Judge reasoning", raw `stage_4_prefilter` ids, "Ask Claude…"); replace docs-path and env-var instructions in publish errors; gate `/feedback` and `/workplan` behind a developer-mode flag.

Pipeline and product correctness
- Plumb effort level into the job (level → `PreFilterOverrides` / routing overrides), or collapse the picker to a budget confirmation.
- Make refinement a job (202 + WebSocket progress + cancel + quota pre-check sized by whether a re-judge is needed); make the snapshot-keyed page the canonical preview with Refine and Approve so child snapshots can be published or refined again; return `parent_snapshot_id` from the projects API and show chains on the Dashboard.
- Add a settings/env switch for the stratified budget; wire `build_image_embedder(settings)` in the runner glue so the embedder setting is actually read.
- Land the two unshipped S-2.10.4 tasks (detection confidence 0.6 / Haar minNeighbors 8, minSize 40; insightface default decision).
- Second-guess: surface the 0.6–0.85 band with Apply/Skip, implement shorten/lengthen/swap via `PlanDirective`, or drop the Tier-M call when the band is unused.
- Add a `reanalyze_refs` lever so refinement can re-run Stage 3 with extra prompt variables (E-2.12 AC still unmet); build the documented `source="feedback"` reservation path or drop the literal.
- RAW photos: add `rawpy` and the `.cr2/.nef/.arw/.dng` extensions, or stop advertising RAW in the folder scan and show a "RAW skipped" count.
- Delete the five dead routed ops (`recommend_effort_level`, `explain_cost`, `explain_upgrade_path`, `orchestrator_reasoning`, `analyze_music_duration_mismatch`), the never-emitted `OrchestratorTurnEvent`, and the empty `api/ws.py` placeholder router; fix the WS docstring path.
- Map "model not found / deprecated" in `_classify_failure` so a retired model ID produces a readable error.
- Add a model-availability probe behind the setup wizard's Test button (and at startup) instead of the stub.
- Video capture time + GPS via ffprobe `creation_time` and timezone normalisation (182-video jobs currently fall back to filename/mtime).
- Decide `reverse_geocoder`: add the dependency (plus its cities data download) so GPS → destination mapping actually runs, or delete the dead code path and stop claiming it in S-2.10.5 / A-026.
- Fix `_ballpark_cost` to use the loaded card; reconcile `tests/test_rate_cards.py` (pins the old 4-5 cards as "the four MVP cards") with `tests/test_routing_config_integrity.py` (bans 4-5) when the lineup is bumped.
- Remove the unused `AnthropicClient.tool_call` primitive (zero callers, zero tests) together with the dead orchestrator plumbing, or keep it only if the E-4.x agent loop is scheduled.
- Local backends are not installed on the dev machine (`insightface`, `torch`, `onnxruntime`, `open_clip`), so `cast_backend=insightface` degrades to the Gemini embedder and ADR-0018 cannot be exercised; the hardware-tier bootstrap must install them deliberately.
- YouTube Shorts was named in the 2026-06-11 vision addendum as a target alongside Instagram Reels but appears in no story or roadmap row; it falls out of 9:16 output (S-3.3.3) and should be named there.
- Add a mid-job cap guard in the router (check before each paid call, raise a classified failure) and route refinement/title-card through the same pre-flight; the pre-job estimate is a ballpark, so the cap is the only real protection.
- Write `cost_summary.json` + `diagnostics.json` for refine child snapshots and sum child costs on the Dashboard.
- Expose `cast_backend`, `cast_analysis_enabled` and `image_embed_backend` in Settings (today the D-044 "config flip" means editing the SQLite settings table by hand).
- Clean up the two orphaned `pending` snapshots left by interrupted jobs; there is no cleanup or resume path.
- Developer API knobs: `/api/jobs/headless` and `/render` build `PreFilterOverrides` with only `quality_threshold` + `target_size`; montage, semantic-dedup, location-cap and stratify knobs are unreachable from any endpoint.
- `docs/OVERVIEW.md` privacy section overstates ("per-project controls", "face-related analysis stays entirely local") against the code; fix alongside the publish claim.

Operations and install
- Commit a lock file (`pip freeze` → requirements-lock) and add upper bounds for `anthropic`, `google-genai`, `mediapipe`; update ADR-0007 (names the retired `google-generativeai` SDK).
- `frontend/dist` is gitignored and not packaged; `pyproject.toml` declares `frontend_dist/**/*` but nothing copies it, so a fresh clone shows "frontend not built". Add a build/copy step or document it prominently.
- `scripts/windows/bootstrap.ps1` and the mac/linux scripts are stubs; README prerequisites omit ffmpeg. `.claude/launch.json` starts only Vite and needs the backend on 8765 separately; `start.ps1` is the complete launcher.
- **Media-cache disk growth (P1):** scene frames and thumbnails are written under `projects/{project_id}/cache/` keyed by content hash but never shared across projects, so the same trip ingested into a new project duplicates ~13 GB; the tree is 92 GB today. Move scene/thumb caches to a shared content-addressed store (the ADR-0006 design already has one for LLM payloads), add disk accounting to Settings, and a cleanup command.
- Telemetry rotation (47 MB / 103,746 lines; the cost summary scans the whole file per job) and LLM-cache GC (101 MB, 13,338 index rows); the ADR-0015 "archive telemetry" Settings button was never built.
- Emit a terminal telemetry event (or mark abandoned on startup) for jobs lost to a restart; today they simply vanish.
- The deterministic floor is ~31 min on a fully cached 1,649-asset set (ingest, hashing, scene detection, embeddings I/O); no perf budget covers it. Stage 7 also pre-renders clips sequentially although the ffmpeg worker class allows two.
- Add a feedback delete endpoint that also tombstones the JSONL (or stop calling the JSONL a mirror).
- Favicon 404 (`/vite.svg` referenced, not in dist). Personal `start-impact-crater.bat` gives the wrong pip hint.
- Media input is a typed server-side absolute path and a music file is mandatory; ship a tiny bundled royalty-free track and a folder picker so first-run users are not blocked.

Security, packaging, licensing, release (found by the completeness critic; none was in the tracker)
- **Local API hardening (before any public URL):** no route or the WebSocket checks authentication or origin; `cli.py` accepts any `--host` without warning; the folder-scan endpoint reads any absolute directory; settings, job submit and publish all mutate or spend. Add a per-install random bearer token injected into the SPA and required on mutating routes and the WS, refuse non-loopback hosts without an explicit flag, and make this a hard prerequisite of the Instagram public-URL decision (expose a single expiring signed media URL, never the API). Add `SECURITY.md`.
- **Secrets at rest:** the Fernet key sits beside the SQLite file and the "restrictive permissions" claim in `crypto.py` is a no-op on Windows NTFS; no backup/restore or key-loss guidance (losing the key bricks stored API keys); connector tokens live in plaintext shell variables. Document key management and a backup procedure; later an `impact-crater backup` command.
- **Delete project / forget media:** no endpoint removes a project's DB rows, cache payloads, scene frames, thumbnails or feedback screenshots; the 92 GB cleanup has no code path, and `api/media.py` globs thumbnails across all projects by content hash, so deleting one project's cache can break another's diagnostics. Build the delete path together with the shared scene cache.
- **Packaging blocker for PyPI:** `prompts/`, `config/llm-routing.yaml`, `config/rate-cards/` and `project/` resolve repo-root-relative (`parents[3]`) and are not in `package-data`; an installed wheel cannot route a single LLM call. Move them under the package or resolve via `importlib.resources`.
- **Third-party ML licensing:** insightface's `buffalo_l` pack is licensed for non-commercial research, so it cannot be a default in a BSL project with a commercial licensor; the same check is owed for BeatNet, open_clip weights, YuNet ONNX and Gemini image-output terms for published title cards. No NOTICE / third-party-licenses file, no `CONTRIBUTING.md` (ADR-0001 promised DCO terms), `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates or dependabot config on a public repo.
- **D-050 violations in machine-readable metadata:** `pyproject.toml` description "AI-driven photo and video curator", classifiers "Development Status :: 1 - Planning" and "License :: Other/Proprietary"; `mkdocs.yml` site description (the search-engine meta description of the public site) and the FastAPI app description say the same.
- **Release engineering:** zero git tags across 77 commits; version `0.0.1` duplicated in `pyproject.toml`, `package.json` and `__init__.py`; no CHANGELOG; `requires-python >= 3.11` and ruff/mypy target py311 while every doc assumes 3.12.
- **Frontend and runtime drift:** vite 5, vitest 2, jsdom 25, `@types/node` 22 (Node 24 in use), tailwind 3, react-router 6 are all a major behind; the backend venv already crossed a major (starlette 1.0 / fastapi 0.136 against a 0.115 floor). The lock-file item must cover both stacks.
- **Operational gaps:** server logs go to console only (post-restart forensics rely on telemetry, which has no "abandoned" marker); the quota day boundary uses local `date.today()` while telemetry and YouTube's quota reset are UTC, so a job spanning midnight sees its cap reset mid-run.
- **OAuth operations:** Google OAuth clients in "Testing" publishing status issue refresh tokens that expire after 7 days, and `youtube.upload` is a sensitive scope (Production implies verification or an unverified-app screen); both the env-var and the planned Settings-stored token break weekly unless this is decided. YouTube's 10,000 units/day ≈ 6 uploads/day caps any multi-artifact package.
- **Stale and heavy assets:** the NotebookLM video, PDF and infographic (~14 MB of binaries in a 21 MB repo) describe the pre-E-2.10 product and assert "hardware-adaptive processing" that does not exist; `scripts/wiki_smoke_test.py` (M1-era, hits real APIs) and two untracked `*-smoke-test.mp4` files sit at the repo root; `docs/dev/M0-SMOKE-TEST.md` is historical. The Pages deploy has not been verified in four months and installs a floating `mkdocs-material`.

### 4.3 Decisions pending (owner calls)

Grouped; each has a recommended default. Full detail with evidence lives in the audit transcript.

**A. MVP closure**
1. Declare I-2 done or amend `MVP.md` pre-flight. Default: amend pre-flight to the actual MVP shape (move N-008 Stage-3 recognition, editable privacy toggles and the profile UI to explicit mvp-hardening or v1 stories), perform one real private YouTube publish, then close E-2.9 → I-2 and open I-3.
2. First real (non-dry-run) YouTube publish. Default: mint `IC_YOUTUBE_*` per `docs/connectors/youtube-setup.md`, set `IC_PUBLISH_DRY_RUN=0` for one session, publish one existing render at `private`, verify the audit entry, flip dry-run back on.
3. ADR-0013 in-app OAuth vs shipped env-var credentials. Default: amend ADR-0013 to accept env-var creds for MVP; build the in-app consent UI once in E-3.3 where it also serves Instagram/Facebook/X.
4. Default publish visibility. ADR-0013 says public, the setup doc says start private, the API defaults to public. Default: API keeps public, UI defaults to last-used (first run private).
5. Define the D-042 "single-video quality mastery" gate measurably. Default: two consecutive fresh renders of two different real trips the owner would publish unchanged (≤ 2 refine passes, zero `incorrect` feedback on Stage 4/5), recorded as a D-NNN.

**B. Model and dependency drift (P0 before any paid run)**
6. Refresh ADR-0009 lineup to current models (Claude 5 family for Tier-M/L; verify Gemini Flash + embedding IDs). Multi-file change: routing yaml, prompt filenames, integrity test, temperature-unsupported set, `model_version` bump to invalidate cache, rate cards.
7. Refresh rate cards (snapshots 2026-05-04 / 2026-06-30) and add the missing `gemini-2.5-flash-image` card; add a test that every routed model has a card.
8. Re-pin or upper-bound SDK and CV dependencies (`anthropic`, `google-genai`, `mediapipe`, `numpy`, `librosa`); update ADR-0007 (names the retired `google-generativeai`).
9. Run a fresh full-scale D-014-style validation after the bump (cache keeps Stages 1–3 cheap; Tier-L re-runs) and make it the new reference arc.
10. Policy for the paid `--integration` suite: run once after the bump and after any SDK upgrade.
11. Implement the real provider key ping in the setup wizard (still an M0 stub).

**C. Architecture-vs-reality (write amendments)**
12. Supersede ADR-0014's never-built `Orchestrator` loop with the shipped harness (deterministic runner + single-shot structured calls); prune the 4 dead routing ops; defer agentic loops to E-4.2.
13. Amend ADR-0012 (librosa-only; BeatNet when torch arrives with E-3.1) and fix MVP.md #8.
14. Face detector going forward. D-044 already records the OpenCV Haar fallback as the decided behaviour (mediapipe 0.10.35 removed `mp.solutions`), so this is not undocumented drift; the open call is accuracy and library choice: drop the dead `mediapipe` dependency, adopt OpenCV YuNet for blur + cast, keep insightface as the upgrade path, and validate on the SW-US cast (amends ADR-0016 / D-044).
15. ADR-0010 deviations: record piexif; decide rawpy (add it or stop advertising RAW); saliency crop vs centre-crop.
16. Decide whether A-018's auto-cast supersedes N-008's manual collage recognition (then cancel S-2.6.2 and repurpose the People page as a naming layer over cast clusters).
17. Privacy toggles: build the three per-project toggles and wire `prepare_for_llm` into Stage 2/3 byte reads (recommended, since remote-first sends images off-device), or document explicitly that images are sent unmodified.
18. Record in ADR-0014's successor that N-009's realisation is the single-call refinement planner; revisit the 10-turn loop in E-4.3.

**D. Gated / deferred mechanisms**
19. Accept ADR-0018 (local CLIP/SigLIP embedder) as the first E-3.1 deliverable; mark S-2.10.8 blocked-by E-3.1 instead of in-progress.
20. Run the ADR-0020 stratified-budget A/B on the SW-US snapshot; decide default ON/OFF; record D-NNN.
21. Pick the v1 local runtime (Ollama recommended), sequenced embedder-first, Ollama-second; write the hardware-tier ADR then.
22. Keep N-011 privacy routing deferred and bundle with E-3.1 (S-2.6.4 → cancel or re-home; its ticked boxes are wrong).
23. Insightface as default cast backend: keep gemini default, auto-suggest insightface when a GPU/≥ 16 GB RAM is detected.
24. Crowd-removal provider (A-019 / S-2.9.7): default to the already-routed Gemini image model for inpainting behind the privacy toggle; stays v2.
25. Post-judge validate-and-reprompt repair loop (D-053): instrument cap-violation counts first; build only if violations recur.
26. Auto-tuning thresholds from feedback (D-045): stay human-in-the-loop until ≥ 50 decision-level items across ≥ 5 trips.

**E. Process and hygiene**
27. Add test CI (ruff, mypy, pytest non-integration, tsc, vitest) and switch skills from `--admin` to `--auto` merge once branch protection requires checks (ADR-0004 revisit trigger).
28. Telemetry rotation (47 MB and growing) and snapshot/render retention policy (31 projects / 42 snapshots / 22 renders) — E-3.5.
29. Triage the 11 `new` feedback items: `show` each, confirm against the post-E-2.12 render, mark `addressed` or `dismissed`.
30. Reconcile tracker drift (E-2.10 → done; S-2.10.8 → blocked; S-2.6.2/S-2.6.4 boxes; S-3.3.1/S-3.3.2 vs landed code; ROADMAP phase table pointing at the existing I-3/I-4/I-5; `workplan_overrides` reconcile).
31. Refresh CLAUDE.md "Decisions locked" (still says stack/MVP/harness/storage/connectors are deferred) and fill the coding-standards section (ruff/mypy/pytest/vitest already enforced).
32. Prune the stale worktree; decide on the untracked `.claude/launch.json` (commit it) and `.scratch/` (keep ignored).
33. PyPI publish timing and `pyproject.toml` metadata (description still says "curator", status "Planning", version 0.0.1).

**F. Roadmap sequencing**
34. Open v1 (I-3 → in-progress) and re-sequence D-039's v1.1–v1.9 given MVP findings (IG/FB connectors already landed; embedder needs the local runtime; quality gate unmet). Default: quality-first v1.1, local runtime v1.2, finish connectors (OAuth UI + X + 9:16) v1.3, then live job.
35. Promote S-2.9.19 (durable job registry) and S-2.9.15 (two-phase pre-filter) to mvp-hardening P1; keep S-2.9.17/S-2.9.18 as the next small hardening items.
36. Later-phase items left as-is: Tier-M provider re-evaluation with eval data, manual `plan.json` override (drop in favour of NL refinement + per-clip actions), proactive Refine on low confidence, render concurrency, native shell, high-privacy mode, music sourcing vendors, pin-to-project, BSL review (v3).

**G. Added by the completeness critic**
37. Google OAuth publishing status for the YouTube client: stay in Testing (refresh tokens expire every 7 days; re-mint weekly) or move to Production (app verification or an unverified-app interstitial for the sensitive `youtube.upload` scope). Default: Production with the unverified-app screen accepted for a personal app; surface token expiry in connector status.
38. Third-party ML asset licensing (D-NNN): insightface `buffalo_l` is non-commercial, so it stays opt-in unless cleared; check BeatNet, open_clip, YuNet, Gemini image-output terms; add a NOTICE file.
39. Local API exposure model: loopback-only by default with an explicit `--allow-remote` flag and a per-install bearer token; the Instagram public URL exposes a signed media URL only. Default: build before any tunnel.
40. Packaging: move `prompts/` and `config/` under the package (default) vs add `package-data` + `importlib.resources` resolution; decide `requires-python` (3.12, matching the docs and wheels) and align ruff/mypy targets; single source of version + CHANGELOG before tagging v0.1.0.
41. Data deletion: a "delete project / forget media" path that removes derived data (DB rows, cache payloads, scene frames, thumbnails, feedback screenshots) and tombstones telemetry; the OVERVIEW privacy text must not promise more than this.
42. Quota day boundary: UTC (matching telemetry and YouTube) vs local; default UTC, documented.
43. NotebookLM assets: regenerate from the rewritten OVERVIEW, relabel "June 2026 preview", or remove; move ~14 MB of binaries out of git (LFS or release assets).

### 4.4 Testing pending

What exists: 61 backend test files / 483 collected (476 pass, 7 integration-gated), every pipeline stage has a dedicated unit test, 10 frontend vitest files / 38 tests, `tsc` clean. What is missing is the top of the pyramid.

**MVP.md pre-flight criteria (10 boxes, all unticked) — evidence check**

| # | Criterion | Status | Evidence / what is needed |
|---|---|---|---|
| 1 | All 9 milestone epics closed | partial | E-2.9 in-progress with 12 unchecked ACs; E-2.10 frontmatter in-progress |
| 2 | D-014 on a real dataset within 2–5 h **and** published to real YouTube | half met | Scale/time half met (60 min + 9 min render, $18.84, 2026-06-18); publish half never attempted (no audit row, even dry-run) |
| 3 | No critical regressions across Stages 1–9 | partial | Unit suite green; no real-data regression run since 2026-07-02; no golden-output harness (`.scratch/eval_headless.py` is ad hoc) |
| 4 | Cost UI real numbers + total **and** per-provider cap enforcement tested | partial | Metering accurate since D-048; cap check is pre-job only; runner-level test covers the total cap only; no mid-job guard |
| 5 | Privacy panel three toggles + ADR-0016 matrix end-to-end | unmet | Toggles hard-coded; transforms have zero callers; 9 unit tests cover a path the product never takes |
| 6 | YouTube upload e2e on a real account, audit entry, all three visibilities | unmet | OAuth unbuilt; tests use a fake transport and assert only `unlisted` |
| 7 | Person library + N-008 with ≥ 3 real persons / ≥ 50 photos | unmet | S-2.6.2 deferred; 1 person row, 0 face photos; re-scope to validating the A-018 cast |
| 8 | Refine produces a meaningfully different result | met live, untested | Pacing, coverage and title-card refinements verified live 2026-06-30/07-01; no automated plan-diff test; `parent.txt` chain never written (chain lives in DB) |
| 9 | Fresh-install wizard run | unmet | `~/.impact-crater` has existed continuously since May; Setup test covers steps 0–1 of 6 |
| 10 | README walkthrough by fresh eyes | unmet | README still describes the M0 dev install |

**Untested or under-tested areas**
- Modules with no direct tests: `jobs/runner_glue.py` (failure classification, job submission), `pipeline/cast_builder.py`, `media/_face_detect.py`, `connectors/facebook.py`.
- API endpoints never requested by a test: `POST /jobs/{id}/cancel`, `WS /jobs/ws/{id}`, `GET /snapshots/{id}/second_guess.json`, `GET /snapshots/{id}/diagnostics` happy path, `GET /connectors/status`, `DELETE /persons/face-photos/{id}`.
- Frontend: no tests for `SnapshotInspect` or `PersonLibrary`; the publish modal, refine submit, wizard steps 2–5 and the cancel call are never driven; no browser e2e.
- Integration tests (3 files, 7 tests) date from 2026-05-04, predate cast / brief intent / title card / Stage 9, still reference `claude-sonnet-4-5`, need keys that are not in `.env.test`, and have no run record since May. They are the only thing that would catch a retired model ID.
- No CI at all; coverage configured without a threshold; no pre-commit.
- No golden-output / quality-regression harness; no perf test (one real datapoint: ~0.46 assets/s on the SW-US set); no restart/resume test; no HEIC decode test beyond extension classification; RAW not ingestible.
- Music-video mode last validated on a real song 2026-06-11, before E-2.11/E-2.12 changed Stage 6.
- ADR-0020 stratified-budget A/B never run (would cost ~$0.02 from cache).
- No full-scale run since PR #72 (the Vegas fix, PlanDirective, cast merge, model bump); E-2.10 / E-2.12 acceptance is verified only on a 55-media project. The current model pins have never produced a full-scale output.
- Publish visibility is tested for `unlisted` only; `private` and `public` paths are untested. The frontend never reads `cost_summary.json`, so per-snapshot cost is invisible on the Inspect page.
- Nothing simulates provider credit exhaustion mid-job, the exact failure that killed the 2026-06-17 cold run after 2h55m.
- The 476-pass result was measured on Windows with the main-repo venv; nothing shows the suite passes on Linux (mediapipe wheel, `scenedetect[opencv-headless]`, apt ffmpeg), which both the planned CI and the Linux install proof assume. `pytest` must run from the repo root (`testpaths = ["tests"]`), with `PYTHONPATH=backend` when testing a worktree.
- Whether starlette 1.0's `FileResponse` serves HTTP Range requests for `render.mp4` (the real question behind S-2.9.17's second acceptance box) has never been checked.
- The Instagram connector's request shape (and whether Meta accepts a 16:9 1080p MP4 as a Reel at all) has never been exercised even with mocked HTTP; the dry-run wrapper never calls Meta.
- The GitHub Pages deploy has no build check in CI and has not been verified since June; `mkdocs build --strict` belongs in CI with `mkdocs-material` pinned.
- `tests/test_rate_cards.py` pins the old 4-5 cards as "the four MVP cards" while the routing-integrity test bans 4-5 IDs; no test cross-checks that every routed model has a rate card (the audit's claim that one exists was refuted).
- S-2.6.5 claims a PersonLibrary + privacy-toggle test that does not exist; 25 done items carry unchecked acceptance boxes, so checkboxes are unreliable in both directions.

**Recommended test additions (in priority order)**
1. `pytest --integration tests/integration/test_real_providers.py` once, with keys, as the very first action of the restart (validates model IDs for cents).
2. A GitHub Actions `ci.yml`: ruff + mypy + pytest (non-integration, with ffmpeg) + `npm ci && npm run typecheck && npm test`; Linux job doubles as the Linux fresh-install proof; then revisit ADR-0004's `--admin`.
3. Golden-output eval: freeze the SW-US headless result as a fixture; promote `.scratch/eval_headless.py` to `scripts/eval_plan.py` with thresholds (video share, chronology back-steps, named-destination coverage, per-viewpoint cap); run on cached results after any Stage 4/5/6 or prompt change.
4. Tests for `_classify_failure` (incl. a new model-not-found branch), cast builder with stubbed detector/embedder, Facebook connector, the six unhit endpoints, refine plan-diff across three messages, child-snapshot artifacts, per-provider cap at runner level, mid-job cap guard.
5. Frontend: PersonLibrary, SnapshotInspect, publish modal → `POST /publish` payload, refine submit, Setup steps 2–5, cancel click; one Playwright smoke submit → progress → preview.
6. Manual: fresh-install run with `IMPACT_CRATER_HOME` pointed at an empty dir; one real private YouTube publish; README walkthrough; music-video re-run on the Zion set; stratified A/B.

### 4.5 Future-looking items (vision catalog) — status and gaps

Delivered from the original vision and the 2026-06 addenda: full-journey Story Video with music; clip extraction and photo cropping to frame; preview → approve → publish gate (code); plain-language refinement; housekeeping skills and the tracker; cheap-first analysis; duplicate/retake suppression; trip cast (analysis half); chronology + rich pre-planning metadata; in-app feedback loop with live diagnostics and screenshots; one-click positioning; mandatory cost preview.

Pending and tracked (by phase):

| Phase | Item | Tracker |
|---|---|---|
| v1 | Local ≤ 32B LLM runtime, hardware tiers, N-002 operation-aware router, functional N-011 privacy routing | E-3.1 (S-3.1.1–3) |
| v1 | Live job: cloud-folder watcher, mobile camera-roll watcher, multi-output orchestration, during-event publish triggers | E-3.2 (S-3.2.1–4) |
| v1 | X connector; per-platform 9:16 / 1:1 formatting + duration caps; watermark mode; in-app OAuth | E-3.3 (S-3.3.1–3) — IG/FB connectors + platform picker already landed untracked |
| v1 | Reference-media style fingerprint + style match as a judge objective + theme library | E-3.4 (S-3.4.1–2) |
| v1 | Multi-version comparison UI; quality floor + override; L4–L5 + full cost dashboard + upgrade-path explanations; manual override / per-image privacy review | E-3.5 (S-3.5.1–4) |
| v1 | Auto photo/video editing (highlights, shadows, contrast, grading) | E-3.6 (S-3.6.1) |
| v1 | Royalty-free starter pack; licensed library; conversational section adjustments | E-3.7 (S-3.7.1–2) |
| v1 | LLM-driven profile re-derivation; "what you've learned" surface | E-3.8 (S-3.8.1–2) |
| v1 | Full reuse-class cache semantics; hit-rate dashboard | E-3.9 (S-3.9.1–2) |
| v1 | Local CLIP/SigLIP embedder weights; two-phase pre-filter; durable job registry; crossfades | S-2.10.8, S-2.9.15, S-2.9.19, S-2.9.4 |
| v2 | Mobile companion app | E-4.1 |
| v2 | Multi-agent harness; conversational refinement at scale | E-4.2, E-4.3 |
| v2 | Generated music | E-4.4 |
| v2 | Trip Package (segmentation, density allocation, N briefs, package preview, overall video + montage) — gated by D-042; every prerequisite now exists | E-4.5 (S-4.5.1–5) |
| v2 | AI crowd removal | S-2.9.7 (ready; blocked on provider choice) |
| v3 | Hosted infra, multi-tenancy/auth/billing, public launch | E-5.1–E-5.3 |

Pending and **untracked** (should become stories):

- Facebook 20+-photo album artifact (original vision; no item anywhere).
- Per-location Instagram Reel artifact (9:16, ≤ 90 s, one per detected location) — the first concrete multi-artifact deliverable.
- Montage mode for a whole video (burst-montage clip type exists; standalone artifact is S-4.5.4 only).
- A-009 auto-captions (locked MVP-lite constraint, zero code).
- M6 second-guess Apply/Skip/Modify UI.
- N-010 profile wiring (events emitted from approve/refine/publish, pre-fill on New Project, reset in Settings, pipeline read-sites).
- Trip-cast review UI: name / promote / demote persons, one-click coverage repair (A-018 remainder).
- "Execution theatre" view with collapse toggle (2026-06-14 addendum).
- Video capture-time + GPS via ffprobe `creation_time` and timezone normalisation (A-021 follow-on; 182-video jobs currently fall back to filename/mtime).
- Snapshot history / branch / revert UI (N-003); project export with face-library exclusion (ROADMAP v1.5).
- A-026 top-locations into the title prompt (unblocked by `destinations.py`).
- A-016/A-017/A-022/A-023/A-024 follow-ons: local blur/motion pre-score, dedup-aggressiveness knob, mild-safety gate and obstruction penalty, feedback → commit linkage, bulk triage.
- Hardware probe (GPU/VRAM/RAM) persisted at setup — shared prerequisite for S-3.1.1, S-2.10.8 and S-2.9.7.
- YouTube Shorts as a named 9:16 target (2026-06-11 addendum; untracked).
- Surface or gate the second-guess self-overrides (never shown to the user; a likely hidden source of "why was X dropped" feedback).
- Rate-card refresh mechanism; acceptance-test matrix for MVP.md constraints #1–#17.

### 4.6 Process / hygiene drift

Tracker (`project/`)
- E-2.10 frontmatter `in-progress` with Children saying S-2.10.5/6/7/8 todo, while BOARD says done 2026-07-01; BOARD lists S-2.10.5 and S-2.10.7 under both "Up Next" and "Recently Done", S-2.10.6 under Backlog, and S-2.10.8 twice.
- Ten done stories (S-2.10.1–7, S-2.12.1–3) have no "done" activity entry; several were closed with "pending" as the last word of their only log line; S-2.10.8 lacks its "stub landed" entry; S-2.9.15 has an empty log and is parented to an initiative.
- D-039 recorded a decision not to create I-3/I-4/I-5 until v1 opens; they were backfilled on 2026-06-14 and the reversal was never logged as a D-NNN.
- I-2 Children is a 2026-05-05 fossil (E-2.4/5/6 listed twice with contradictory statuses, E-2.7/8/9 "todo", E-2.10/11/12 absent, "Nine epics"). E-2.9 lists 6 of 20 children. E-2.5/6/7/8 still say "stories filed when this epic opens"; E-2.7 and E-2.8 closed with zero stories. E-2.12 has no Children section.
- "Done" epics E-2.5/6/7/8 and 19 done stories carry unchecked acceptance criteria; S-2.6.2/S-2.6.4 have every box ticked but the code does not exist.
- Vocabulary drift: `phase: mvp-hardening` (11 items) and statuses `backlog` / `ready` / `deferred` are undefined in `project/README.md`, the templates and ROADMAP; seven v1-phase stories sit under mvp-phase epics, so the in-app workplan roll-ups are wrong.
- `project/README.md:147` still says the work-tracker "never auto-merges" (contradicts ADR-0004).
- Shipped-but-untracked: S-3.3.1 / S-3.3.2 (connectors), the platform picker, the dry-run gate.

Docs
- `README.md` describes 2026-05-03 ("MVP build in progress", "16 ADRs, 39 D-NNN, 11 novel", "M0 ships the empty bootable shell", GROOMED_FEATURES and MVP.md "stub"); actual: 20 ADRs, D-056, N-015, A-026, D-014 passed.
- `CLAUDE.md` still says tech stack / MVP scope / coding standards are deferred or "not yet chosen"; the Decisions-locked table has no tech-stack row.
- `docs/OVERVIEW.md` (the only public page) says videos are "published to YouTube" and that a cross-project "learning profile" is in use; neither has ever happened. It also lists Instagram/Facebook as near-term though their connectors shipped, and carries no last-updated stamp. This is a public-trust fix.
- `ROADMAP.md` phase index says I-3/I-4/I-5 are "created when v1 opens" (they exist since 2026-06-14), ignores the D-014 pass, has stale tallies and no mvp-hardening section.
- `GROOMED_FEATURES.md` has no delivered markers for anything after 2026-06-11 and still tags NL refinement as v2. `ARCHITECTURE.md` says "sixteen ADRs" and never cites ADR-0017..0020, PlanDirective or ReservationSet. `PIPELINE_DATAFLOW.md` says "last synced 2026-06-18", its Stage 9 section and diagram still describe the M6 single-strategy refine, and its prompt appendix names `*-4-5` files that no longer exist. NOVEL_IDEAS / RECOMMENDED_ADDITIONS headers still say 11 N / 15 A.
- ADR-0018 still `proposed`; ADR-0009 lineup table names Sonnet/Opus 4.7 while config routes 4.6/4.8; ADR-0013 describes the superseded OAuth+SQLite model with no D-NNN recording the dry-run default; ADR-0012 still says Madmom; ADR-0014 describes a never-built Orchestrator.
- RAW_VISION addenda stop at 2026-06-14; the 2026-06-30 round-2 feedback and the "refinement must handle arbitrary NL" instruction exist only inside tracker files; `docs/vision/notes/` was never created. `docs/connectors/*.md` is linked from nowhere.

Process
- 11 feedback items still `new`. Mapping: #2, #7, #9, #10, #11, #12 → shipped (S-2.10.2/3/4/5); #3 → dismiss (verdict was "correct"); #1, #5, #6, #8 → symptom-fixed, root cause open (ADR-0018 embedder, ADR-0020 A/B). `feedback.jsonl` (13 rows incl. a `__probe__` row and an id 13) has diverged from the DB (11 rows).
- No post-fix full re-run of the SW-US job is recorded, so E-2.10 / E-2.12 acceptance stays unverified.
- `workplan_overrides` is empty (nothing to reconcile).
- Stale detached worktree `trusting-rhodes-bb0b37` (its only delta is already on master). `.scratch/` (~16 MB; E-2.12's log cites `.scratch/refinement_design.json`) and `.claude/launch.json` are untracked and un-ignored.
- Stop hook and both skills intact, but the last two sessions' board/doc updates rode inside feature PRs, and `settings.local.json` carries a session-specific allow entry.
- No test CI (only the Pages workflow), so ADR-0004's `--admin` auto-merge revisit trigger has never fired.
- No decision records whether the MVP phase is closed and v1 open; "mvp-hardening" absorbed three epics ad hoc.
- `pyproject.toml`, `mkdocs.yml` and the FastAPI app description still call the product an "AI-driven photo and video curator" (D-050), with "Development Status :: 1 - Planning" and a proprietary-license classifier.
- Zero git tags; the version string is duplicated in three files; no CHANGELOG; `requires-python >= 3.11` while the docs and wheels assume 3.12.
- `scripts/wiki_smoke_test.py` (M1-era, hits real APIs) and two untracked `*-smoke-test.mp4` files at the repo root; `docs/dev/M0-SMOKE-TEST.md` is historical; the NotebookLM PDF/video/infographic describe the June product and weigh ~14 MB.
- No `CONTRIBUTING.md` (ADR-0001 promised DCO terms), `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates or dependabot config on a public repo; no NOTICE / third-party-licenses file.

---

## 5. Phase-wise plan

Three independent planners (ship-first, quality-mastery-first, roadmap-fidelity) were scored and merged. The spine is **ship-first** (it is the only ordering that never asks for paid or multi-hour work before the thing that would waste it is fixed), with the quality-first plan's instruments grafted in early (the measurable gate is written and a $0 eval harness built before any heuristic changes) and the roadmap-fidelity plan's two audit-proven corrections adopted as explicit decisions (local embedder before the Ollama runtime; 9:16 render target before any reel). Every deviation from the locked ROADMAP order is recorded as a D-NNN, as D-039 requires. Estimates: S = under one session (~1–2 h of Claude Code), M = one session, L = 2–3 sessions, XL = 4+. Paid API calls happen only in Phases 1, 3, 4 and 6, and only after the owner approves a stated spend envelope.

### At a glance

| Phase | Name | Outcome | Sessions | Paid? |
|---|---|---|---|---|
| 0 | Resume honestly | Tracker, docs, ADRs, feedback inbox and repo match the code; closure + model decisions taken; dead code gone | 2–3 | No |
| 1 | Run and publish for real | Current model lineup with cache invalidation and pre-spend ping; first dry-run and real private YouTube publish; Settings credential flow; any snapshot publishable; CI; I-2 closed; v0.1.0 | 5–7 | ~$6 + one small job |
| 2 | Instruments + daily-driver hardening | Written D-058 quality gate; $0 eval harness + golden set; durable job registry; refine as a job; mid-job cap; token-based estimate; privacy honesty; disk/telemetry bounded; profile emitters; test gaps closed | 8–11 | No |
| 3 | Single-video quality mastery | Fresh full-scale reference run; root-cause fixes with before/after evidence (local visual embedder, two-phase pre-filter, calibrated floors, YuNet detector, cast review, video chronology, taste polish, auto-grading, theme presets); D-058 gate run and recorded | 12–16 | 2–3 full runs (~$20–50 each cold) |
| 4 | v1 opens, publish-and-artifact-first | 9:16 / 1:1 render targets, per-location reel, photo album, live Instagram/Facebook (+X if wanted), captions, profile UI, power-user bundle, music pack, style fingerprint (stretch), PyPI | 14–18 | Live publishes only |
| 5 | Local-first | Ollama ≤ 32B runtime, operation-aware router, functional privacy routing + full toggles, local cost model, Linux CI | 10–14 | No |
| 6 | Trip Package pilot + live job | Package of artifacts from one click behind one gate; watched-folder live job; mobile, multi-agent, chat, generated music, crowd removal, hosted v3 explicitly parked behind it | 16–24 | Package runs |

### Phase 0 — Resume honestly: drift, decisions, hygiene, zero spend

Goal: everything the next session reads is true; no paid call, no job submitted.

1. **One work-tracker reconciliation PR** [M] — regenerate BOARD from frontmatter and fix every contradiction in §4.6: E-2.10 → done (2026-07-01, PR #72); I-2 Children → E-2.1..E-2.12 with dates; E-2.9 Children → all 20; E-2.5/E-2.6 Children from stories, E-2.7/E-2.8 "delivered epic-level", E-2.12 gets Children; E-2.6 relabelled "done at MVP scope" listing the unwired parts; S-2.9.17 → re-scoped to its second box (first frame shows promptly; verify Range support on starlette 1.0) since the faststart box is already true; S-2.10.4 → reopened as partial for its two unlanded tasks; S-2.9.7 → todo under a new E-4.6; S-2.9.15 → E-3.9; S-2.9.4 → E-3.6; S-2.9.19 → mvp-hardening P1; S-2.10.8 → todo/v1 blocked-by E-3.1; S-2.6.2 boxes unchecked and re-homed, S-2.6.4 canceled as superseded by S-3.1.3; S-3.3.1 → done "dry-run only"; S-3.3.2 split (Facebook done / new S-3.3.4 XConnector); E-3.3 → in-progress; child-prefix fix; define `backlog`/`ready`/`deferred` + `mvp-hardening`; fix README:147; "verified by" or "deferred → vN" annotation on every unchecked box of a done item; correct S-2.6.5's false test claim; file the new stories named in this plan, including local API hardening, delete-project/forget-media and wheel packaging of prompts/config.
2. **D-057 and an honest `MVP.md` pre-flight** [S] — tick #8 (four live refine children) with evidence; leave #3 ("no critical regressions") open until the Phase 3 reference run passes the Phase 2 eval harness (unit tests alone are not evidence for it); record the D-014 facts on #2, leaving only its publish half open; keep #6 for Phase 1; re-scope #5 (privacy toggles) to Phase 2 minimum + Phase 5 full, #7 (N-008) to "superseded by the A-018 cast; validate on ≥ 3 known persons" in Phase 3, #9/#10 to Phase 2; amend M6 (auto-applied internally; reconfirm UI Phase 3), M7 (env-var path accepted), M8 (emitters Phase 2, UI Phase 4). Widen the amendment to the "must do" table (#4 resumable, #8 Madmom, #10 single coordinator with tool calls → ADR-0021, #13 privacy controls, #16 captions) and the "must NOT do" list ("only YouTube" contradicts the shipped IG/FB connectors). D-057 also records that 2026-06-11 → 07-01 was an mvp-hardening phase and that the I-3/I-4/I-5 backfill reversed the D-039 clause without a decision.
3. **Close the A-023 loop** [S] — triage the 11 feedback rows (2, 7, 9, 10, 11, 12 addressed citing S-2.10.2/3/4/5 and PR #72; 3 dismissed; 1, 5, 6, 8 triaged pointing at ADR-0018 and the ADR-0020 A/B); declare SQLite authoritative; fix the "mirror" wording in CLAUDE.md.
4. **Public-trust docs PR** [M] — OVERVIEW (publish, encrypted creds, audit trail, learning profile, per-project privacy, on-device routing claims; IG/FB "available behind your own credentials"; as-of stamp), README (status, counts, ffmpeg, connector docs links), CLAUDE.md (locked stack row, coding standards, session-loop additions: verify model IDs, reconcile feedback), ROADMAP phase index + mvp-hardening paragraph, GROOMED delivered markers, ARCHITECTURE amendments section, PIPELINE_DATAFLOW Stage 9 + sync stamp, N/A header counts, RAW_VISION 2026-06-30 addenda, `docs/vision/notes/`.
5. **ADR truth bundle** [M] — ADR-0018 → accepted-staged; ADR-0013 amendment (env-var creds + dry-run default + IG public-URL requirement layered beside the dormant OAuth/Fernet path, which the Phase 1 Connect-in-Settings story builds on; UI default visibility private-first); ADR-0009 "current pins" table pointing at the yaml, covering the image model; ADR-0012 librosa-only accepted, BeatNet at E-3.1; **ADR-0021** superseding ADR-0014's harness section (deterministic runner + single-shot structured calls; N-009 realised as the single-call refinement planner; agentic loop deferred to E-4.3/E-4.2); ADR-0010 note (piexif, Haar, no rawpy, centre crop); ADR-0007 google-genai; ADR-0020 A/B scheduled Phase 2; a key-management section (Fernet key location, Windows ACL hardening or explicit acceptance, backup/restore of `~/.impact-crater`, key-loss recovery); a D-NNN on third-party ML asset licensing (insightface opt-in unless cleared) with a NOTICE file; `CONTRIBUTING.md` (DCO per ADR-0001), `SECURITY.md`, `CODE_OF_CONDUCT.md`, dependabot config.
6. **Repo + session hygiene** [S] — remove the stale worktree; promote `.scratch/refinement_design.json`, `designs.json`, `critique.md` to `docs/design/` and ignore the rest; commit `.claude/launch.json` with a backend attach entry; fix the session-specific allow entry and make the hook also check `git status --porcelain project/ docs/`; commit a lock file + upper bounds for `anthropic`/`google-genai`/`mediapipe`/`numpy`/`librosa` and pin or test the already-installed starlette 1.0 / fastapi 0.136 major; `npm audit`, `engines` field, `@types/node` matching Node 24; fix the `.bat` hint and favicon; delete or promote `scripts/wiki_smoke_test.py` and the two root `*-smoke-test.mp4`; mark `docs/dev/M0-SMOKE-TEST.md` historical; fix the D-050 wording in `pyproject.toml`, `mkdocs.yml` and the FastAPI app description; decide the NotebookLM assets (regenerate, relabel "June 2026 preview", or remove) and move the ~14 MB of binaries out of git.
7. **Dead-code sweep** [S] — delete `api/ws.py` + its include, the six routed-but-unimplemented ops (keep `analyze_music_duration_mismatch` only if the fade/loop/truncate picker is scheduled), `OrchestratorTurnEvent`, `AnthropicClient.tool_call`/`stream_chat`, the runner tier entry; fix the WS docstring and the stale Madmom/mediapipe docstrings.
8. **Owner-side $0 check** [S] — which Claude / Gemini IDs still resolve (provider console or models endpoint); pick Tier-M/L/S, embedding and image targets; approve a Phase 1 spend envelope (~$1 integration suite + ~$5 smoke job).

Decisions: D-057 shape; ADR-0013 ratify env-var path; ADR-0021 supersede the Orchestrator loop; ADR-0012 librosa; ADR-0018 accepted-staged; model targets + pinned `model_version` tokens; feedback store authoritative = SQLite; tracker vocabulary definitions and "child inherits epic phase"; `.scratch` promotion; keep or delete `analyze_music_duration_mismatch`; UI default visibility private-first.

Exit: BOARD regenerated with zero contradictions (scripted tally); `MVP.md` has exactly one unticked gate (the real publish) and every other box ticked or re-scoped with a tracker ID; feedback inbox shows zero unexplained `new`; OVERVIEW/README/CLAUDE.md truthful with an as-of stamp; ADRs amended and ADR-0021 written; worktree gone, lock file committed, zero dead ops; model decision + spend envelope recorded; both Stop-hook skills complete every session.

### Phase 1 — Run and publish for real: current models, first live YouTube publish, CI, close I-2

1. **S-2.10.9 model-lineup bump** [L] — yaml IDs with pinned `model_version` (not `latest`); prompt renames; data-driven temperature guard; rate cards for new IDs + the missing `gemini-2.5-flash-image` card; replace the 4-5 pins in both tests with "every routed model has a card" and "no model older than family N" guards; fix the integration test's `sonnet-4-5`; route `_caption_for_embedding` through the yaml; model-not-found branch in `_classify_failure`; fix `_ballpark_cost`; real provider ping behind the wizard Test button and at job submit.
2. **Disk check + owner-approved purge, then re-baseline** [S] — before the smoke job (which writes new per-project scene caches) check free disk and purge the cache directories of the 13 snapshot-less projects, verifying no other project's diagnostics reference those hashes (the thumbnail lookup globs across projects); then `pytest --integration` once from the repo root; one small Zion job through the UI incl. title card and one refine; record wall-clock and cost.
3. **`ci.yml` + `--admin` → `--auto`** [M] — ruff, mypy, pytest (non-integration, with ffmpeg) on ubuntu as well as the owner's Windows baseline, `npm ci` + typecheck + vitest + build, `mkdocs build --strict` with `mkdocs-material` pinned, coverage; branch protection on status checks; record the D-NNN. The Linux job is the first proof the suite passes anywhere but Windows.
3b. **Local API hardening** [M] — per-install bearer token injected into the SPA and required on mutating routes and the WebSocket; origin check on the WS; refuse non-loopback `--host` without `--allow-remote`; `SECURITY.md`. Hard prerequisite of S-3.3.5 and of any Instagram public URL (which must expose a single expiring signed media URL, never the API).
3c. **OAuth operations decision** — Google OAuth client publishing status (Testing = 7-day refresh expiry; Production = verification or unverified-app screen for the sensitive `youtube.upload` scope); surface token expiry and last refresh in connector status; record the ~6 uploads/day quota as a budget input for Phases 4 and 6.
4. **First publish** [S] — one dry-run per platform through the UI (three `(dry-run)` audit rows), then owner-side: mint `IC_YOUTUBE_*`, dry-run off, publish snapshot `b4b73c7b1fe044b7` at `private`, confirm the audit row and URL, flip dry-run back. Fallback if the owner cannot: D-NNN amending D-014 to dry-run-verified and move the real publish to Phase 4.
5. **Publish UX honesty** [M] — Approve caption from live connector status; dry-run as a Settings toggle (no restart); first-run visibility private; title/description defaults from title card and brief; Settings links instead of repo paths.
6. **S-3.3.5 Connect YouTube in Settings** [M] — loopback OAuth writing `connector_credentials`, Connect/Disconnect UI, status from DB-or-env; slip fallback: Fernet-encrypted Settings form.
7. **SnapshotInspect as canonical preview** [M] — Approve & publish + Refine on any snapshot; `parent_snapshot_id` in the projects API; chain on the Dashboard.
8. **Audit-log viewer** [S]. 9. **Close E-2.9 and I-2; tag v0.1.0** [S] — single source of version (pyproject + `__init__` + `package.json` via a bump script), a CHANGELOG seeded from PR titles #1–#74, `requires-python` aligned to 3.12 with ruff/mypy targets.

Exit: a private video uploaded by the app is visible in YouTube Studio; ≥ 1 live and ≥ 3 dry-run audit rows; connectors status connected via the DB path with no env vars; one fresh job on the new IDs; no 4-x IDs outside historical rate cards; CI required on master; refined children publishable and re-refinable; MVP pre-flight #2/#6 ticked; E-2.9 and I-2 done.

### Phase 2 — Instruments + daily-driver hardening

Split into **2a** (items 1–6 and 9: instruments + durability, the hard gate for Phase 3) and **2b** (the rest: honesty + hygiene, which may interleave with early Phase 3 work).

1. **D-058: the measurable single-video gate** [S] — two consecutive fresh renders of two different real trips, each publishable unchanged or after ≤ 2 refine passes, zero `incorrect` Stage 4/5 feedback after inspection, eval thresholds green; decide whether A-007 / style / auto-editing stay inside the gate.
2. **Eval harness + golden set (new E-3.10)** [L] — `scripts/eval_plan.py` with D-058 thresholds on frozen SW-US + Zion fixtures; `pytest -m eval` on cached results in CI; owner-labelled golden set exported from the feedback table; cap-violation counters in `diagnostics.json`.
3. **Persist the job registry (S-2.9.19)** [L] — rehydrate finished jobs from snapshots on boot; persist in-progress state + per-stage checkpoints; mark orphans abandoned in telemetry; `/jobs/:id` → Inspect when a snapshot exists; clean the two pending snapshots; persist a rotating server log under `~/.impact-crater/logs`.
4. **Refinement as a job** [M] — 202 + WS + cancel; quota pre-check sized by re-judge; child `cost_summary.json` + `diagnostics.json`; Dashboard sums child costs.
5. **Mid-job cap guard** [M] — before every paid call, total + per-provider; credit-exhaustion simulation test; align the quota day boundary with a documented timezone (UTC, matching telemetry and YouTube).
6. **Token-aware estimate + real effort levels (S-2.9.18)** [M] — priors from 103k telemetry records; show a range; plumb `level_id` into real behaviour or collapse the picker.
7. **Privacy honesty minimum** [M] — explicit `strip_exif` at the rendition point + regression test; Stage 3 never sends originals; plain-language "What we send to the AI" copy; blur-faces becomes a real CV-only toggle as soon as the YuNet detector lands (item 10); only privacy *routing* waits for a local LLM (Phase 5). The OVERVIEW must not promise more than what the delete path (item 9) can honour.
8. **Vocabulary sweep** [S] — Keepers / Story selection / Why these moments; label stage 0 and the title-card stage; gate developer pages.
9. **Disk + telemetry hygiene + delete path** [L] — shared content-addressed scene cache (with a sidecar/thumb path migration for the existing 24 snapshots and a content-addressed thumbnail lookup, since `api/media.py` globs across projects today); a "delete project / forget media" endpoint + UI that removes DB rows, cache payloads, scene frames, thumbnails and feedback screenshots and tombstones telemetry; run the 92 GB cleanup through that path; telemetry rotation + index; keep-last-N retention never deleting published snapshots; Settings "clean up". Must precede Phase 3 runs.
9b. **Package prompts and config into the wheel** [M] — move `prompts/`, `config/llm-routing.yaml` and `config/rate-cards/` under the package (or add `package-data` + `importlib.resources` resolution in `prompts.py`, `router.py`, `rate_cards.py`, `api/workplan.py`); fix the `setup.cfg` docstring; the Phase 4 PyPI exit becomes "fresh venv, `pip install` from the wheel with no checkout, wizard + small job succeed".
10. **Dependency decisions** [M] — add `reverse_geocoder` (+ data) or delete the path; replace dead mediapipe with OpenCV YuNet; D-NNN amending ADR-0016 / D-044.
11. **RAW decode or stop advertising RAW** [S]; real HEIC fixture.
12. **Fresh-install verification on Windows + README walkthrough + minimal `bootstrap.ps1` + package `frontend/dist`** [M].
13. **Fill the test pyramid** [L] — the four untested modules, six unhit endpoints, frontend gaps, music-video unit tests, a mocked-HTTP test of the Instagram request shape (never exercised, even by dry-run), and a Range-request test for `render.mp4` serving.
14. **Wire the five profile emitters + derive at job end** [S]. 15. **Second-guess visibility** [S] — read-only in Inspect, counters, shorten/lengthen via PlanDirective. 16. **Make the stratified budget reachable + run the cached A/B + D-NNN** [S]. 17. **S-2.10.4 residuals** [S]. 18. **Bundled CC0 track + folder/file picker** [S]. 19. **Feedback → fix linkage (`addressed_by`)** [S].

Exit: D-058 written and on BOARD; eval harness green in CI at $0; golden set for ≥ 2 trips; restart loses nothing and reports interrupted jobs; refine async with artifacts; cap guard proven; estimate within ±30 %; privacy copy truthful with an EXIF-free test; disk bounded and re-runs add no scene frames; profile log receiving events; stratified default recorded; test gaps closed.

### Phase 3 — Single-video quality mastery, then the gate

1. **Fresh full SW-US run on the new lineup + Zion music-video re-validation** [M, ~$20–50] — tick E-2.10 / E-2.12 acceptance; measure cold wall-clock; re-verify feedback 1, 5, 6, 8.
2. **Hardware probe + real local image embedder (S-2.10.8, ADR-0018 → accepted)** [L] — open_clip ViT-L/14 on GPU, ViT-B/32 CPU fallback; distinct cache namespace; re-tuned cosine against the golden set; brings torch.
3. **Two-phase pre-filter (S-2.9.15)** [L] — ≥ 40 % Tier-M saving proven by kept-set overlap.
4. **Quality-floor calibration (S-3.5.2, A-007)** [M] — mild-safety gate, obstruction penalty, specialness calibration, "the AI is unsure about X" hint.
5. **Cast quality + review UI** [L] — YuNet default, insightface offered only as opt-in unless the licensing D-NNN clears its model pack (the `buffalo_l` weights are non-commercial), backends in Settings, cast review (name / promote / demote, one-click coverage repair); N-008 decision (default: cancel S-2.6.2, People page becomes the naming layer) after measuring cast precision on named persons rather than asserting it.
6. **Feedback → reservation auto-wiring** [M]. 7. **Video capture time + GPS via ffprobe; A-026 top locations in the title** [S]. 8. **Render taste polish** [M] — crossfade below ~80 bpm, Ken Burns opt-in, density shaping, optional music-mismatch picker. 9. **Per-scene auto grading (E-3.6)** [L]. 10. **Theme library as presets** [M]. 11. **Compare + history view (S-3.5.1)** [M]. 12. **Second-guess Apply/Skip or disable; repair loop only if counters warrant** [M]. 13. **L4 effort level** [S]. 14. **Execution-theatre view (optional)** [M]. 15. **Tier-M provider comparison on 50 shots** [S].
16. **Run the D-058 gate** [M] — two real trips; record MET (opens Phase 6) or NOT MET with the failing metric and a story.

Exit: reference run recorded and acceptance ticked; every merged Stage 4–7 change carries equal-or-better eval metrics; the Grand Canyon fixture collapses to one keeper; Tier-M spend per 1,000 assets down ≥ 40 %; YuNet default; cast review shipped; feedback inbox empty after re-verification; gate verdict recorded as a D-NNN.

### Phase 4 — v1 opens, publish-and-artifact-first

D-NNN opening I-3 re-sequenced (E-3.3 → E-3.5 → E-3.8 → E-3.7 → E-3.9 → E-3.4/E-3.6 remainder; E-3.1 in Phase 5; E-3.2 in Phase 6). Items: verify Graph API Reels aspect/duration requirements and Facebook video limits first, then Stage 7 honours `RenderPlan.output_*` for 9:16 / 1:1 with saliency crop, duration caps (Reels ≤ 90 s, Shorts ≤ 60 s), watermark [L]; per-location Reel artifact [L]; photo-album artifact + Facebook multi-photo post [M]; first live Instagram/Facebook posts with Meta Connect and the public-URL decision [M]; XConnector if still wanted [L]; resumable uploads + audit signing [M]; captions MVP-lite (description, hashtags, alt text, `.srt`) [M]; profile UI (pre-fill, reset, "what you've learned", read-sites; LLM re-derivation after ≥ 20 jobs) [M]; power-user bundle (per-clip remove/replace, cost dashboard with rate-card refresh, L5, upgrade-path explanations, per-image privacy review, per-project privacy override, export, path-move recovery) [L]; music pack + conversational section lever [M]; style fingerprint (stretch, official APIs only) [XL]; cache reuse classes + hit-rate dashboard + perf smoke, starting with a concrete first GC rule: purge payloads for the retired model IDs [M]; PyPI release from the packaged wheel, proven by a fresh venv with no checkout [S]. The Instagram public-URL decision depends on the Phase 1 API hardening and exposes a signed media URL only.

Exit: one job yields a 16:9 video + ≥ 1 reel + 1 album, each approvable and publishable; live posts on Instagram and Facebook; captions editable at publish; profile visibly learns; 0.1.0 on PyPI; E-3.3/E-3.5/E-3.7/E-3.8/E-3.9 done.

### Phase 5 — Local-first (E-3.1)

Ollama runtime behind `LocalLLMClient` with the ≤ 32B cap and hardware-tier lineup (vision-capable for Stage 2/3; Tier-L judge remote by policy) [XL]; operation-aware router (N-002) with per-op overrides and degraded mode [L]; N-011 privacy routing + the full three-toggle matrix per project, `privacy_class` populated [M]; local compute cost model [S]; BeatNet downbeats and insightface default where hardware allows [M]; Linux CI job + mac/linux bootstrap [M].

Exit: a full job runs Stage 2/3 on the owner's GPU within 2× remote wall-clock and $0 remote spend for those ops; privacy matrix enforced with six tests; MVP constraint #13 true; E-3.1 done; I-3 closes except E-3.2.

### Phase 6 — Trip Package pilot + live job (opened only on the gate-met D-NNN)

D-NNN declaring the gate met and opening E-4.5 as a deterministic pilot; multi-output orchestration (one analysis pass → N briefs) [L]; trip segmentation [L]; density-driven allocation [M]; package plan through the single-video pipeline with per-artifact budget and eval [L]; overall video + montage mode [M]; package preview with per-artifact approve/refine/publish [L]; cloud-folder watcher + during-event triggers preserving the gate [M]; parallel renders [S]; crowd removal with a provider decision (optional) [L].

**Explicitly parked until the package ships:** mobile camera-roll watcher and companion app (S-3.2.2, E-4.1), multi-agent harness (E-4.2, first a D-NNN asking whether E-2.12's lever loop suffices), multi-turn chat refinement with the twice-deferred tool loop and `reanalyze_refs` lever (E-4.3), generated music (E-4.4), hosted multi-tenant v3 (I-5), BSL change-date review, second-reviewer/CODEOWNERS, Tauri shell, feedback auto-tuning (stay human-in-the-loop until ≥ 50 items across ≥ 5 trips).

Exit: one real multi-day trip → one click → package (overall video + ≥ 2 per-location videos/reels + photo album + montage) within budget, every artifact passing the D-058 metrics and approved from the package preview; published to ≥ 2 platforms with audit rows per artifact; a watched folder feeds a live job with the gate intact; RAW_VISION's original artifact list carries delivered markers.

### Risks the plan is built around

- Model retirement discovered mid-job (Phase 0 $0 check, Phase 1 pinned versions + pre-spend ping + error mapping).
- Spend: a cold full run is ~$50 and the only cold run died on credit exhaustion; Anthropic is ~99 % of spend; per-provider caps unset (Phase 2 mid-job guard, Phase 3 two-phase pre-filter, explicit approval per run).
- Owner time is the bottleneck: Google Cloud/OAuth setup, YouTube's ~6 uploads/day quota, golden-set labelling, gate runs, Meta/X accounts (~2–4 owner-hours per phase).
- Disk: 92 GB with ~13 GB duplicated per re-run (Phase 2 shared cache before Phase 3 runs).
- Restart loss is invisible until S-2.9.19 lands: keep the server up through a run; no backend commits mid-job.
- Tracker evidence is unreliable in both directions; the Stop hook must also check for unhoused `project/` and `docs/` edits.
- Dependency drift (floor-only pins); torch adds ~2 GB in Phase 3; unknown GPU class may shrink Phase 5 to hybrid local/remote.
- Gate definition: too strict defers the north star indefinitely, too loose multiplies poor quality across N artifacts; D-058 pairs numeric thresholds with the owner's verdict, time-boxed to two trips.
- Scope creep from 35 placeholder stories and ~30 untracked deferrals: nothing outside Phases 0–2 lands before its phase.
- Public trust: the GitHub Pages overview overstates capability today; Phase 0 fixes it first.
- Exposure: the Instagram tunnel would expose the unauthenticated API until the Phase 1 hardening lands; Google OAuth Testing-mode tokens expire weekly; insightface's model licence blocks it as a default; frontend majors are a version behind; there is no delete path for derived personal data.
- Rough velocity: Phases 0–2 ≈ 6–9 weeks at 2–4 sessions/week; the Trip Package pilot is on the order of 70–90 sessions away. These estimates are not calibrated against the repo's measured velocity (E-2.1 → E-2.12 shipped between 2026-05-03 and 2026-07-01 in 77 commits); calibrate them after Phase 0.

---

## 6. Handoff prompt for the next session

Paste the block below into a fresh Claude Code session opened at `D:\DEV\ClaudeProjects\ImpactCrater`. It covers Phase 0, session 1 of 2–3; it spends no money.

```text
Resume Impact Crater after the ~4-month pause. Read CLAUDE.md, project/BOARD.md and
docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md (the audited landscape + 7-phase plan from 2026-10-24).
Treat that document as the authoritative to-do list for this restart: do not re-audit what it already
verified, but confirm anything you change against the code. This session is Phase 0 ("Resume honestly"),
zero spend: make no paid API call and submit no job. Every change goes branch -> PR -> squash-merge per
ADR-0004; before each PR run `.venv/Scripts/python.exe -m pytest -q` FROM THE REPO ROOT (testpaths is
tests/; expect 476 passed / 7 skipped) and `cd frontend && npm run typecheck && npm test` (38). Project-tracker edits follow the work-tracker skill's rules, docs edits the
knowledge-curator's.

Do these in order, each as its own PR:

1. Hygiene chore PR. Remove the stale worktree (`git worktree remove .claude/worktrees/trusting-rhodes-bb0b37
   && git worktree prune`); move .scratch/refinement_design.json, designs.json and critique.md into
   docs/design/ (E-2.12's log cites them) and add .scratch/ to .gitignore; commit .claude/launch.json with a
   url-only backend attach entry; replace the session-specific allow entry in .claude/settings.local.json
   with Bash(touch .claude/state/housekept-*); commit requirements-lock.txt from `pip freeze` and add upper
   bounds for anthropic / google-genai / mediapipe / numpy / librosa (note starlette 1.0 / fastapi 0.136
   are already installed against a 0.115 floor); fix start-impact-crater.bat's pip hint and the /vite.svg
   favicon 404; delete or promote scripts/wiki_smoke_test.py and the two untracked *-smoke-test.mp4 at the
   repo root; fix the D-050 wording in pyproject.toml (description, Development Status and License
   classifiers), mkdocs.yml site_description and the FastAPI app description.

2. Tracker reconciliation PR (Phase 0 item 1 of the landscape doc, section 5). E-2.10 -> done
   (2026-07-01, PR #72); rewrite I-2 Children to E-2.1..E-2.12 with dates; E-2.9 Children -> all 20
   stories; fill E-2.5/E-2.6 Children, mark E-2.7/E-2.8 "delivered epic-level", add Children to E-2.12;
   relabel E-2.6 "done at MVP scope" listing the unwired parts (privacy transforms, N-008 collage,
   N-011 routing); S-2.9.17 -> re-scope to its second acceptance box only (faststart is already at
   stage7_render.py:524; the Content-Disposition cause was fixed in PR #40; what remains unverified is
   Range support in starlette 1.0 for render.mp4); S-2.10.4 -> reopen as partial for its two unlanded
   tasks; S-2.9.7 ready -> todo under a NEW E-4.6 (crowd removal, blocked on a provider decision);
   S-2.9.15 -> re-parent E-3.9; S-2.9.4 -> E-3.6; S-2.9.19 -> mvp-hardening P1; S-2.10.8 -> todo/v1
   blocked-by E-3.1; S-2.6.2 uncheck the false boxes and re-home under E-3.1; S-2.6.4 -> canceled
   (superseded by S-3.1.3); S-3.3.1 -> done "env-var creds, dry-run only, never live-tested"; split
   S-3.3.2 into Facebook (done) and a NEW S-3.3.4 XConnector (todo); E-3.3 -> in-progress; add the ten
   missing "done (PR #72)" activity entries (S-2.10.1-7, S-2.12.1-3); sed the 35 `- E-x.y.z` child
   prefixes under E-3.x/E-4.x/E-5.x to `- S-`; define backlog / ready / deferred and mvp-hardening in
   project/README.md and TEMPLATES; adopt "child inherits epic phase"; fix project/README.md:147 ("never
   auto-merges"); annotate every unchecked acceptance box on a done item with "verified by ..." or
   "deferred -> vN (date)"; correct S-2.6.5's false test claim. File NEW stories for: S-2.10.9
   model-lineup bump (mirror of S-2.10.7, see landscape Phase 1 item 1), S-3.3.5 Connect YouTube in
   Settings, E-3.10 quality eval harness + golden set, mid-job quota guard, shared content-addressed scene
   cache + disk accounting, profile emitters, refine-as-job + publish-from-any-snapshot, effort-level
   plumbing, privacy honesty minimum, per-location Reel artifact, Facebook photo-album artifact,
   auto-captions (A-009), hardware probe, cast review UI, test CI, local API hardening (bearer token +
   loopback-only default), delete-project / forget-media path, wheel packaging of prompts/ and config/.
   Then regenerate BOARD.md from frontmatter with a 2026-10-24 header and verify with a scripted status
   tally.

3. Feedback triage. `.venv/Scripts/python.exe scripts/feedback.py show <id>` for ids 1,2,3,5-12; mark
   2,7,9,10,11,12 addressed (S-2.10.2/3/4/5, PR #72), 3 dismissed (Claude test entry), 1,5,6,8 triaged
   with a note pointing at ADR-0018/S-2.10.8 and the ADR-0020 A/B. In CLAUDE.md, state that the SQLite
   feedback table is authoritative and feedback.jsonl is an append-only event log, not a mirror.

4. Decisions + MVP.md. Append D-057 to docs/decisions/DECISIONS_LOG.md: MVP closes on an amended
   pre-flight once the real publish lands; 2026-06-11..07-01 was mvp-hardening; the I-3/I-4/I-5 backfill
   on 2026-06-14 reversed the D-039 clause (DECISIONS_LOG:982) without a decision; v1 will open
   re-sequenced per the landscape plan. Amend docs/roadmap/MVP.md pre-flight (lines 107-120): tick #8
   (four live refine children 2026-07-01: 5724f522 / 8d3c4146 / ae220245 / c9a36fd8); leave #3 open with
   a note that it is ticked only when a fresh full-scale run passes the Phase 2 eval harness (unit tests
   are not evidence of no regressions); record the D-014 facts on #2 (1,663 assets; 60 min warm resume + 9 min render for $18.84
   after a 2h55m cold run that died on credit exhaustion; cold-equivalent ~4 h; ~$50 total) leaving only
   its publish half open; keep #6 for Phase 1; re-scope #5 (privacy toggles) to Phase 2 minimum / Phase 5
   full, #7 (N-008) to "superseded by the A-018 cast; validate on >=3 known persons" in Phase 3, #9/#10
   to Phase 2; amend M6 (auto-applied >0.85 internally; reconfirm UI Phase 3), M7 (env-var credential
   path accepted; see ADR-0013 amendment), M8 (emitters Phase 2, UI Phase 4). Also correct the "must do"
   table rows #4 (resumable: unmet, S-2.9.19), #8 (Madmom -> librosa), #10 (single coordinator with tool
   calls -> the shipped deterministic runner, ADR-0021), #13 (privacy controls: not enforced), #16
   (captions: zero code) and the "must NOT do" line "only YouTube" (IG/FB connectors shipped). Every
   re-scope carries a date and a tracker ID.

5. Public-trust docs PR (knowledge-curator rules). docs/OVERVIEW.md: stop claiming videos are "published
   to YouTube", "encrypted credential storage and a full publishing audit trail", a "learning profile",
   per-project privacy controls and on-device routing until they are true; say "can publish once you
   connect an account; dry-run by default"; move Instagram/Facebook to "available behind your own Meta
   credentials"; add "Reflects the application as of 2026-10-24". README.md: status (D-014 curate->preview
   passed 2026-06-18; hardening through 2026-07-01; restart plan link), counts (20 ADRs / 56 decisions /
   15 novel ideas / 29 additions), ffmpeg prerequisite, link docs/connectors/. CLAUDE.md: replace the
   "all deferred" / "not yet chosen" lines with the locked stack (Python 3.12 + FastAPI + React/Vite/TS
   per ADR-0005, SQLite ADR-0006, remote-first routing ADR-0007/0009, librosa, ffmpeg, env-var
   connectors), fill the coding-standards section (ruff / mypy strict / pytest / vitest), add "verify model
   IDs are still served" and "reconcile feedback" to the session loop. ROADMAP.md phase index (I-3/I-4/I-5
   exist; D-014 passed; mvp-hardening paragraph; tallies). GROOMED_FEATURES delivered markers for
   everything after 2026-06-11 and retag NL refinement from v2 to delivered. ARCHITECTURE.md "Amendments
   since 2026-05-03" naming ADR-0017..0020, PlanDirective, ReservationSet. PIPELINE_DATAFLOW Stage 9
   rewritten around RefinementOutcome -> child snapshot, sync stamp bumped. NOVEL_IDEAS /
   RECOMMENDED_ADDITIONS header counts. Dated verbatim RAW_VISION addenda for the two 2026-06-30
   instructions (round-2 output feedback; "refinement must handle arbitrary NL requests") and create
   docs/vision/notes/.

6. Ask me two things that cost nothing and unblock Phase 1, then stop: (a) which Claude / Gemini model
   IDs currently resolve for my keys (I will check the provider consoles) and my choice of Tier-M / Tier-L
   / Tier-S / embedding / image targets plus a Phase 1 spend envelope (~$1 integration suite + ~$5 smoke
   job); (b) whether I will do docs/connectors/youtube-setup.md Step 1 (enable YouTube Data API v3,
   create a Desktop OAuth client) before the next session.

Queue for session 2: the ADR truth bundle (amend ADR-0007/0009/0010/0012/0013/0018/0020; write ADR-0021
superseding ADR-0014's Orchestrator loop; a key-management section; a D-NNN on third-party ML asset
licensing with a NOTICE file; CONTRIBUTING.md with DCO, SECURITY.md, CODE_OF_CONDUCT.md, dependabot) and
the dead-code sweep (api/ws.py, six unimplemented routed ops, OrchestratorTurnEvent,
AnthropicClient.tool_call/stream_chat, stale Madmom/mediapipe docstrings). Verify the GitHub Pages deploy
is green and shows the new as-of stamp.
Session 3 opens Phase 1 with S-2.10.9 (model-lineup bump with pinned model_version, rate cards, data-driven
temperature guard, model-not-found mapping, real wizard key ping) followed by `pytest --integration` and
one Zion smoke job, then the first dry-run and real private YouTube publish.

Rules: never commit to master directly; never --no-verify; no pip/npm installs without asking; restart
the detached dev server after backend commits before UI-testing. End by running /knowledge-curator and
/work-tracker so the housekept marker is written. Report what you finished, what you could not verify,
and the exact next item.
```
