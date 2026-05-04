# Board

> **Last updated:** 2026-05-04 — **E-2.2 (M1 Headless curation through Stage 5) DONE.** All 8 stories closed in one session. The full headless pipeline (Stages 1-5) returns a structured ArcJudgment via `POST /api/jobs/headless` against real Anthropic Opus + Google Flash in ~19s on a 4-photo smoke test. 139/139 tests green (133 unit + 6 integration). **E-2.3 (M2 render + standard mode) now Up Next.**
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.3](./epics/E-2.3-render-and-standard-mode.md) | Render + standard mode (M2) | Epic | P0 | mvp | E-2.2 done — ready |

## Backlog (mvp-phase, queued)

The remaining 6 MVP epic shells under [I-2 MVP](./initiatives/I-2-mvp.md).

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.4](./epics/E-2.4-ui-mvp-loop-closed.md) | UI MVP loop closed (M3) | Epic | P0 | mvp | E-2.3 |
| [E-2.5](./epics/E-2.5-music-video-mode-and-section-to-media-nl.md) | Music-video mode + section-to-media NL (M4) | Epic | P0 | mvp | E-2.4 |
| [E-2.6](./epics/E-2.6-person-library-and-privacy-panel.md) | Person library + privacy panel (M5) | Epic | P0 | mvp | E-2.4 |
| [E-2.7](./epics/E-2.7-agentic-refinement-and-second-guess.md) | Agentic refinement + second-guess (M6) | Epic | P0 | mvp | E-2.4 + E-2.6 |
| [E-2.8](./epics/E-2.8-youtube-publish.md) | YouTube publish (M7) | Epic | P0 | mvp | E-2.3 + E-2.4 |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project profile + polish + D-014 validation (M8 + M9) | Epic | P0 | mvp | E-2.1..E-2.8 |

## Recently Done (last session)

| ID | Title | Type | Done |
|---|---|---|---|
| **[E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md)** | **Headless curation through Stage 5 (M1) — full LLM stack + Stages 1-5 + headless API** | Epic | 2026-05-04 |
| [S-2.2.1](./stories/S-2.2.1-llm-client-protocol-and-providers.md) | LLMClient protocol + Anthropic + Google providers | Story | 2026-05-04 |
| [S-2.2.2](./stories/S-2.2.2-router-config-prompts-cache.md) | LLMRouter + routing config + prompts + cache | Story | 2026-05-04 |
| [S-2.2.3](./stories/S-2.2.3-telemetry-and-quota.md) | Telemetry + JobCostSummary + dual-cap quota | Story | 2026-05-04 |
| [S-2.2.4](./stories/S-2.2.4-worker-pool.md) | Worker pool (cpu/ffmpeg/network) | Story | 2026-05-04 |
| [S-2.2.5](./stories/S-2.2.5-stage1-ingest.md) | Stage 1 ingest + content-hash + scenes | Story | 2026-05-04 |
| [S-2.2.6](./stories/S-2.2.6-stages-2-and-3.md) | Stages 2 + 3 (bulk ops + rich metadata) | Story | 2026-05-04 |
| [S-2.2.7](./stories/S-2.2.7-stage-4-prefilter.md) | Stage 4 pre-filter (deterministic) | Story | 2026-05-04 |
| [S-2.2.8](./stories/S-2.2.8-stage-5-judge-and-headless-endpoint.md) | Stage 5 judge + POST /api/jobs/headless | Story | 2026-05-04 |
| [E-2.1](./epics/E-2.1-scaffolding.md) | Scaffolding (M0) — first commit of code | Epic | 2026-05-03 |
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation — scaffolding-phase exit | Initiative | 2026-05-03 |
| [E-1.4](./epics/E-1.4-roadmap-and-mvp-scoping.md) | Roadmap and MVP scoping | Epic | 2026-05-03 |

---

## Initiative index

| ID | Title | Status | Phase |
|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | **done** (2026-05-03) | scaffolding |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | **in-progress** (2026-05-03; M0 + M1 done) | mvp |
| (I-3 v1) | v1 — Local-first + live job + multi-platform + style + polish | (created when v1 opens) | v1 |
| (I-4 v2) | v2 — Mobile + multi-agent + conversational + generated music | (created when v2 opens) | v2 |
| (I-5 v3) | v3 — Hosted multi-tenant SaaS | (created when v3 opens) | v3 |
