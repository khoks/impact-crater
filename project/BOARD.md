# Board

> **Last updated:** 2026-06-11 (second pass) — **Dashboard gap closed.** After the morning's validation hot-fixes (S-2.9.1, PRs #35–#37, D-040/D-041), the user hit the dashboard stub live ("can't see already submitted and completed jobs"). **S-2.9.2 + S-2.9.3 shipped same-day:** real `GET /api/projects` (DB-backed, snapshots + has_render), `GET /api/jobs` session list, Dashboard rewrite (session-jobs strip, project cards, inline render playback), name/brief upsert at submit, and the `Content-Disposition: inline` fix without which Chrome refuses to play render.mp4 in any `<video>` (also unblocks JobPreview). Verified live in Chrome: 11 projects listed, both Zion renders play inline. **346 backend + 33 frontend tests green.** Remaining under E-2.9: S-2.9.4 crossfades (parked v1) + the user-side D-014 1000-photo validation run. **Third pass: 2026-06-11 feature grooming** — A-016..A-020 + N-012/N-013 + D-042 (Trip Package north star, gated on single-video quality); S-2.9.5/S-2.9.6 filed as the first v1 quality stories.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project profile + polish + **D-014 validation** (reopened 2026-06-11) | Epic | P0 | mvp |

## Up Next (Ready)

(empty — S-2.9.4 is parked at v1; D-014 validation is user-side)

## Backlog (queued)

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [S-2.9.7](./stories/S-2.9.7-ai-crowd-removal.md) | AI crowd removal — inpaint non-group people (remote default / local optional, D-044) | Story | P3 | v2 |
| [S-2.9.4](./stories/S-2.9.4-crossfade-transitions-slow-tempo.md) | Crossfade transitions on slow-tempo music (ADR-0011/0012) | Story | P3 | v1 |

> **2026-06-11 prep-phase overhaul (D-043):** the preparation phase was rebuilt before the heavier features. **Delivered:** A-021 media chronology (EXIF/filename/mtime reconciliation + GPS read; the judge now orders forward-in-time), A-022 rich-metadata enrichment (shot type, per-person expression, safety, specialness, obstructions), A-016 cheap-first analysis (~47× smaller payloads), A-017 best-of-burst semantic dedup.
> **2026-06-11 auto trip cast (D-044):** A-018 analysis half delivered — detect→embed→cluster→group/crowd-by-recurrence-breadth→coverage report, pluggable backends (gemini cloud default / insightface optional local); also fixed face detection (mediapipe 0.10.35 dropped `mp.solutions`, which had silently disabled privacy-blur too). **Next:** A-019 crowd removal (remote-API default / local-generative optional per D-044) builds on the cast. Trip Package (A-020/N-013, v2) stays gated on single-video quality (D-042).

## Recently Done (this session)

| ID | Title | Type | Done |
|---|---|---|---|
| **[S-2.9.9](./stories/S-2.9.9-developer-tracker-pages.md)** | **Developer tracker pages — feedback tracker + workplan tracker (editable priority) [A-024/D-047]** | Story | 2026-06-14 |
| **[S-2.9.8](./stories/S-2.9.8-in-app-feedback-loop.md)** | **In-app feedback loop — per-phase diagnostics + decision-level feedback; +live-during-execution + page screenshots [A-023/N-015/D-045/D-046]** | Story | 2026-06-14 |
| **A-018 / N-012** | **Auto trip cast — face inventory + group/crowd + coverage (analysis half) [D-044]** | Feature | 2026-06-11 |
| **[S-2.9.5](./stories/S-2.9.5-cheap-first-analysis-hardening.md)** | **Cheap-first analysis (1024px renditions + scene subdivision) [D-043]** | Story | 2026-06-11 |
| **[S-2.9.6](./stories/S-2.9.6-semantic-near-duplicate-suppression.md)** | **Best-of-burst semantic dedup (time-windowed) [D-043]** | Story | 2026-06-11 |
| **A-021 / A-022** | **Media chronology + GPS + rich-metadata enrichment (prep-phase overhaul, D-043)** | Feature | 2026-06-11 |
| **[S-2.9.2](./stories/S-2.9.2-dashboard-project-list-render-history.md)** | **Dashboard project list + render history + inline playback (+ Content-Disposition fix)** | Story | 2026-06-11 |
| **[S-2.9.3](./stories/S-2.9.3-persist-project-brief-and-name.md)** | **Persist brief + name on project rows at job submit** | Story | 2026-06-11 |
| **[S-2.9.1](./stories/S-2.9.1-validation-hotfixes-2026-06-11.md)** | **Validation hot-fixes 2026-06-11 — cache poisoning (D-040), beat-snap (D-041), audio fade, EXIF; PRs #35–#37** | Story | 2026-06-11 |

## Previously Done (last sessions)

| ID | Title | Type | Done |
|---|---|---|---|
| **[E-2.6](./epics/E-2.6-person-library-and-privacy-panel.md)** | **Person library + privacy panel (M5) — N-008 collage builder + EXIF strip + face blur + UI; 2 stories deferred-to-v1** | Epic | 2026-05-05 |
| [S-2.6.1, S-2.6.3, S-2.6.5](./stories/) | M5 stories shipped | Stories | 2026-05-05 |
| **[E-2.5](./epics/E-2.5-music-video-mode-and-section-to-media-nl.md)** | **Music-video mode + section-to-media NL (M4) — librosa MusicAnalyzer + cut grid + Stage 5/6 wiring + UI** | Epic | 2026-05-05 |
| [S-2.5.1..3](./stories/) | M4 stories (analyzer + cut-grid + pipeline wiring + frontend) | Stories | 2026-05-05 |
| **[E-2.4](./epics/E-2.4-ui-mvp-loop-closed.md)** | **UI MVP loop closed (M3) — React UI + async jobs + WS + preview** | Epic | 2026-05-05 |
| [S-2.4.1](./stories/S-2.4.1-async-jobs-ws-folder-scan.md) | Async jobs + WS + folder scan + cost preview | Story | 2026-05-05 |
| [S-2.4.2](./stories/S-2.4.2-dashboard-and-new-project.md) | Dashboard + New Project flow | Story | 2026-05-05 |
| [S-2.4.3](./stories/S-2.4.3-effort-level-and-cost-preview.md) | Effort-level UX + cost preview + submit | Story | 2026-05-05 |
| [S-2.4.4](./stories/S-2.4.4-progress-and-preview.md) | In-job progress + live spend + preview UI | Story | 2026-05-05 |
| [S-2.4.5](./stories/S-2.4.5-settings-panel.md) | Settings panel | Story | 2026-05-05 |
| **[E-2.3](./epics/E-2.3-render-and-standard-mode.md)** | **Render + standard mode (M2) — Stages 6-7 + render API** | Epic | 2026-05-04 |
| [S-2.3.1..4](./stories/) | M2 stories (ffmpeg resolver + Stage 6 + Stage 7 + render API) | Stories | 2026-05-04 |
| **[E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md)** | **Headless curation through Stage 5 (M1) — full LLM stack + Stages 1-5 + headless API** | Epic | 2026-05-04 |
| [S-2.2.1..8](./stories/) | M1 stories (LLMClient + router + telemetry + quota + worker pool + Stages 1-5 + headless endpoint) | Stories | 2026-05-04 |
| [E-2.1](./epics/E-2.1-scaffolding.md) | Scaffolding (M0) — first commit of code | Epic | 2026-05-03 |

---

## Initiative index

| ID | Title | Status | Phase |
|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | **done** (2026-05-03) | scaffolding |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | **in-progress** (E-2.9 reopened 2026-06-11 for D-014 validation; M0..M8 code done) | mvp |
| (I-3 v1) | v1 — Local-first + live job + multi-platform + style + polish | (created when v1 opens) | v1 |
| (I-4 v2) | v2 — Mobile + multi-agent + conversational + generated music | (created when v2 opens) | v2 |
| (I-5 v3) | v3 — Hosted multi-tenant SaaS | (created when v3 opens) | v3 |
