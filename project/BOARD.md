# Board

> **Last updated:** 2026-05-03 — E-1.4 picked up. Round-1 (MVP execution roadmap) S-1.4.1 + T-1.4.1.1..3 in flight. Producing: MVP.md final lock with 9-milestone partition; new I-2 MVP initiative + E-2.1..E-2.9 epic shells; D-036 + D-037 + D-038. Velocity = AI-assisted full-time aggressive (4-8 weeks calendar). Round 2 (ROADMAP.md final lock with v1/v2/v3 sequencing) opens after this round closes.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | Initiative | P0 | scaffolding |
| [E-1.4](./epics/E-1.4-roadmap-and-mvp-scoping.md) | Roadmap and MVP scoping | Epic | P1 | scaffolding |
| [S-1.4.1](./stories/S-1.4.1-mvp-execution-roadmap.md) | MVP execution roadmap (round 1 of E-1.4) | Story | P1 | scaffolding |
| [T-1.4.1.1](./tasks/T-1.4.1.1-mvp-md-final-lock.md) | MVP.md final lock | Task | P1 | scaffolding |
| [T-1.4.1.2](./tasks/T-1.4.1.2-create-i2-mvp-initiative-and-epics.md) | Create I-2 MVP initiative + 9 epic shells | Task | P1 | scaffolding |
| [T-1.4.1.3](./tasks/T-1.4.1.3-file-d-036-d-037-d-038.md) | File D-036 + D-037 + D-038 in DECISIONS_LOG | Task | P1 | scaffolding |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| (round 2 of E-1.4) | ROADMAP.md final lock — v1 / v2 / v3 sequencing | Story (TBC) | P1 | scaffolding | round 1 done |
| **I-2 MVP / E-2.1 Scaffolding (M0)** | First commit of code — `pip install impact-crater` works; CLI starts FastAPI; React shell loads; first-time-setup wizard; SQLite schema initializes | Epic | P0 | mvp | E-1.4 done |

## Backlog (mvp-phase, queued)

The MVP work container is the new [I-2 MVP](./initiatives/I-2-mvp.md) initiative with 9 epic shells (one per milestone M0..M9). Promotes to Up Next when E-1.4 closes (round 2 ROADMAP.md still pending).

| ID | Title | Type | Priority | Phase | Blocked by |
|---|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp | E-1.4 done |
| [E-2.1](./epics/E-2.1-scaffolding.md) | Scaffolding (M0) | Epic | P0 | mvp | I-2 promoted |
| [E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md) | Headless curation through Stage 5 (M1) | Epic | P0 | mvp | E-2.1 |
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
| [E-1.3](./epics/E-1.3-architecture-grooming.md) | Architecture grooming | Epic | 2026-05-03 |
| [S-1.3.3](./stories/S-1.3.3-architecture-grooming-round-3.md) | Architecture grooming — round 3: connectors + harness + cross-cutting | Story | 2026-05-03 |
| [T-1.3.3.1..4](./tasks/) | E-1.3 round-3 tasks (ADR-0013..0016) | Tasks | 2026-05-03 |
| [S-1.3.2](./stories/S-1.3.2-architecture-grooming-round-2.md) | Architecture grooming — round 2: media + curation | Story | 2026-05-02 |
| [T-1.3.2.1..3](./tasks/) | E-1.3 round-2 tasks (ADR-0010..0012) | Tasks | 2026-05-02 |
| [S-1.3.1](./stories/S-1.3.1-architecture-grooming-round-1.md) | Architecture grooming — round 1: foundation + LLM stack | Story | 2026-04-28 |
| [T-1.3.1.1..5](./tasks/) | E-1.3 round-1 tasks (ADR-0005..0009) | Tasks | 2026-04-28 |
| [E-1.5](./epics/E-1.5-auto-merge-policy.md) | Auto-merge policy for skill and feature PRs | Epic | 2026-04-26 |
| [E-1.2](./epics/E-1.2-vision-grooming.md) | Vision grooming | Epic | 2026-04-26 |

---

## Initiative index

| ID | Title | Status | Phase |
|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | in-progress | scaffolding |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | backlog | mvp |
