# Board

> **Last updated:** 2026-05-03 — **E-2.1 (M0 Scaffolding) DONE.** First commit of application code on master. ~50 files: Python backend (cli + FastAPI app + storage layer with 12-table SQLite schema + Fernet crypto + setup-wizard API) + Vite/TypeScript/Tailwind frontend (router + Zustand + 6-step wizard) + cross-OS dev launchers + 10-step `M0-SMOKE-TEST.md`. Post-merge verification by user via the smoke-test doc. **E-2.2 (M1 headless curation through Stage 5) is now Up Next.**
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| **[E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md) Headless curation through Stage 5 (M1)** | LLM stack (Anthropic + Google + LLMRouter + telemetry + worker pool) + pipeline Stages 1–5 → ArcJudgment JSON | Epic | P0 | mvp | — (E-2.1 done) |

## Backlog (mvp-phase, queued)

The remaining 7 MVP epic shells under [I-2 MVP](./initiatives/I-2-mvp.md).

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [E-2.3](./epics/E-2.3-render-and-standard-mode.md) | Render + standard mode (M2) | Epic | P0 | mvp | E-2.2 |
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
