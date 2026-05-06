# Board

> **Last updated:** 2026-05-05 — **E-2.6 (M5 person library + privacy) DONE at MVP scope.** Person library backend (CRUD + reference-collage builder per N-008), privacy pipeline (piexif EXIF strip + mediapipe face-blur with per-project cache; ADR-0010 named pyexiv2 + dlib but those don't ship Python-3.12 wheels), frontend person library page + dashboard "People" link. **2 of 5 stories deferred to v1**: S-2.6.2 (Stage 3 N-008 integration — invasive LLMClient changes) and S-2.6.4 (N-011 privacy-routing schema — meaningful only with ADR-0008 local-LLM destination). Today: **247 tests green** (219 backend unit + 28 frontend unit). M0+M1+M2+M3+M4+M5 done; **E-2.7 (M6 agentic refinement) is Up Next**.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.7](./epics/E-2.7-agentic-refinement-and-second-guess.md) | Agentic refinement + second-guess (M6) | Epic | P0 | mvp | E-2.6 done — ready |

## Backlog (mvp-phase, queued)

The remaining MVP epic shells under [I-2 MVP](./initiatives/I-2-mvp.md).

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.8](./epics/E-2.8-youtube-publish.md) | YouTube publish (M7) | Epic | P0 | mvp | E-2.3 + E-2.4 |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project profile + polish + D-014 validation (M8 + M9) | Epic | P0 | mvp | E-2.1..E-2.8 |

## Recently Done (last session)

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
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | **in-progress** (2026-05-03; M0 + M1 + M2 + M3 + M4 + M5 done) | mvp |
| (I-3 v1) | v1 — Local-first + live job + multi-platform + style + polish | (created when v1 opens) | v1 |
| (I-4 v2) | v2 — Mobile + multi-agent + conversational + generated music | (created when v2 opens) | v2 |
| (I-5 v3) | v3 — Hosted multi-tenant SaaS | (created when v3 opens) | v3 |
