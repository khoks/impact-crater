# Board

> **Last updated:** 2026-05-04 — **E-2.3 (M2 Render + standard mode) DONE.** All 4 stories closed in the same session as E-2.2 (M1). The full M2 pipeline (Stages 1-7) returns a rendered MP4 via `POST /api/jobs/render` against real Anthropic Opus + Google Flash + ffmpeg in ~22s on a 3-photo + 4s-tone smoke test. ffmpeg 8.1 installed via winget. **169/169 tests green** (162 unit + 7 integration). M0+M1+M2 are all behind us; **E-2.4 (M3 UI MVP loop closed) is now Up Next.**
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.4](./epics/E-2.4-ui-mvp-loop-closed.md) | UI MVP loop closed (M3) | Epic | P0 | mvp | E-2.3 done — ready |

## Backlog (mvp-phase, queued)

The remaining 6 MVP epic shells under [I-2 MVP](./initiatives/I-2-mvp.md).

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.5](./epics/E-2.5-music-video-mode-and-section-to-media-nl.md) | Music-video mode + section-to-media NL (M4) | Epic | P0 | mvp | E-2.4 |
| [E-2.6](./epics/E-2.6-person-library-and-privacy-panel.md) | Person library + privacy panel (M5) | Epic | P0 | mvp | E-2.4 |
| [E-2.7](./epics/E-2.7-agentic-refinement-and-second-guess.md) | Agentic refinement + second-guess (M6) | Epic | P0 | mvp | E-2.4 + E-2.6 |
| [E-2.8](./epics/E-2.8-youtube-publish.md) | YouTube publish (M7) | Epic | P0 | mvp | E-2.3 + E-2.4 |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project profile + polish + D-014 validation (M8 + M9) | Epic | P0 | mvp | E-2.1..E-2.8 |

## Recently Done (last session)

| ID | Title | Type | Done |
|---|---|---|---|
| **[E-2.3](./epics/E-2.3-render-and-standard-mode.md)** | **Render + standard mode (M2) — Stages 6-7 + render API** | Epic | 2026-05-04 |
| [S-2.3.1](./stories/S-2.3.1-ffmpeg-resolver-and-probe.md) | ffmpeg/ffprobe resolver + audio probe | Story | 2026-05-04 |
| [S-2.3.2](./stories/S-2.3.2-stage6-plan-compile.md) | Stage 6 plan compile + RenderPlan | Story | 2026-05-04 |
| [S-2.3.3](./stories/S-2.3.3-stage7-render.md) | Stage 7 ffmpeg render + standard music + loudnorm | Story | 2026-05-04 |
| [S-2.3.4](./stories/S-2.3.4-render-endpoint.md) | POST /api/jobs/render + JobCostSummary | Story | 2026-05-04 |
| **[E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md)** | **Headless curation through Stage 5 (M1) — full LLM stack + Stages 1-5 + headless API** | Epic | 2026-05-04 |
| [S-2.2.1..8](./stories/) | M1 stories (LLMClient + router + telemetry + quota + worker pool + Stages 1-5 + headless endpoint) | Stories | 2026-05-04 |
| [E-2.1](./epics/E-2.1-scaffolding.md) | Scaffolding (M0) — first commit of code | Epic | 2026-05-03 |
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation — scaffolding-phase exit | Initiative | 2026-05-03 |

---

## Initiative index

| ID | Title | Status | Phase |
|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | **done** (2026-05-03) | scaffolding |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | **in-progress** (2026-05-03; M0 + M1 + M2 done) | mvp |
| (I-3 v1) | v1 — Local-first + live job + multi-platform + style + polish | (created when v1 opens) | v1 |
| (I-4 v2) | v2 — Mobile + multi-agent + conversational + generated music | (created when v2 opens) | v2 |
| (I-5 v3) | v3 — Hosted multi-tenant SaaS | (created when v3 opens) | v3 |
