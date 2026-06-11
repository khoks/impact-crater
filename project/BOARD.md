# Board

> **Last updated:** 2026-06-11 — **E-2.9 reopened for D-014 validation hot-fixes.** First real-media validation run (33 Zion photos + 1 video + mp3, both modes) surfaced 4 blocking bugs, all fixed and verified same-session as **S-2.9.1** (PRs #35–#37; decisions D-040/D-041): LLM-cache payload-path poisoning (the `stage4_empty_candidate_set` failure), music-video timeline truncation (25.3s of a 60s target), audio fade-out never playing, EXIF portrait photos pillarboxed/sideways. Retest green: standard 56.3s with fade + smart-crop; music video 60.0s with 11/12 beat-aligned cuts. **342 backend tests green.** Validation gaps filed: S-2.9.2 dashboard project list (P1), S-2.9.3 brief persistence (P2), S-2.9.4 crossfades (parked v1). D-014's real 1000-photo run remains user-side.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project profile + polish + **D-014 validation** (reopened 2026-06-11) | Epic | P0 | mvp |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [S-2.9.2](./stories/S-2.9.2-dashboard-project-list-render-history.md) | Dashboard project list + render history (replace M0 stub) | Story | P1 | mvp |
| [S-2.9.3](./stories/S-2.9.3-persist-project-brief-and-name.md) | Persist brief + name on project rows at job submit | Story | P2 | mvp |

## Backlog (queued)

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [S-2.9.4](./stories/S-2.9.4-crossfade-transitions-slow-tempo.md) | Crossfade transitions on slow-tempo music (ADR-0011/0012) | Story | P3 | v1 |

## Recently Done (this session)

| ID | Title | Type | Done |
|---|---|---|---|
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
