# Board

> **Last updated:** 2026-05-04 — **E-2.2 (M1 Headless curation through Stage 5) in flight.** M0 verified Windows-side (PR #12 fixups landed). 8 stories under E-2.2 cover the full LLM stack (LLMClient + Anthropic + Google + LLMRouter + telemetry + dual-cap quota + worker pool) and pipeline Stages 1-5 (ingest → bulk ops → rich metadata → pre-filter → N-001 narrative-arc judgment) → `POST /api/jobs/headless` returning structured ArcJudgment JSON. Real-API integration tests behind `--integration` marker.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |
| [E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md) | Headless curation through Stage 5 (M1) | Epic | P0 | mvp |
| [S-2.2.1](./stories/S-2.2.1-llm-client-protocol-and-providers.md) | LLMClient protocol + Anthropic + Google providers | Story | P0 | mvp |
| [S-2.2.2](./stories/S-2.2.2-router-config-prompts-cache.md) | LLMRouter + routing config + prompts + cache | Story | P0 | mvp |
| [S-2.2.3](./stories/S-2.2.3-telemetry-and-quota.md) | Telemetry + JobCostSummary + dual-cap quota | Story | P0 | mvp |
| [S-2.2.4](./stories/S-2.2.4-worker-pool.md) | Worker pool (cpu/ffmpeg/network) | Story | P0 | mvp |
| [S-2.2.5](./stories/S-2.2.5-stage1-ingest.md) | Stage 1 ingest + content-hash + scenes | Story | P0 | mvp |
| [S-2.2.6](./stories/S-2.2.6-stages-2-and-3.md) | Stages 2 + 3 (bulk ops + rich metadata) | Story | P0 | mvp |
| [S-2.2.7](./stories/S-2.2.7-stage-4-prefilter.md) | Stage 4 pre-filter (deterministic) | Story | P0 | mvp |
| [S-2.2.8](./stories/S-2.2.8-stage-5-judge-and-headless-endpoint.md) | Stage 5 judge + POST /api/jobs/headless | Story | P0 | mvp |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.3](./epics/E-2.3-render-and-standard-mode.md) | Render + standard mode (M2) | Epic | P0 | mvp | E-2.2 done |

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
| **[E-2.1](./epics/E-2.1-scaffolding.md)** | **Scaffolding (M0) — first commit of code** | Epic | 2026-05-03 |
| [S-2.1.1..6](./stories/) | M0 stories (repo skeleton + FastAPI + CLI + storage + crypto + React shell + setup wizard + dev launchers + smoke-test doc) | Stories | 2026-05-03 |
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation — scaffolding-phase exit | Initiative | 2026-05-03 |
| [E-1.4](./epics/E-1.4-roadmap-and-mvp-scoping.md) | Roadmap and MVP scoping | Epic | 2026-05-03 |
| [E-1.3](./epics/E-1.3-architecture-grooming.md) | Architecture grooming | Epic | 2026-05-03 |
| [E-1.5](./epics/E-1.5-auto-merge-policy.md) | Auto-merge policy | Epic | 2026-04-26 |
| [E-1.2](./epics/E-1.2-vision-grooming.md) | Vision grooming | Epic | 2026-04-26 |

---

## Initiative index

| ID | Title | Status | Phase |
|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | **done** (2026-05-03) | scaffolding |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | **in-progress** (2026-05-03) | mvp |
| (I-3 v1) | v1 — Local-first + live job + multi-platform + style + polish | (created when v1 opens) | v1 |
| (I-4 v2) | v2 — Mobile + multi-agent + conversational + generated music | (created when v2 opens) | v2 |
| (I-5 v3) | v3 — Hosted multi-tenant SaaS | (created when v3 opens) | v3 |
