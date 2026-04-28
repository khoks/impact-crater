---
id: I-1
title: Project foundation
type: initiative
status: in-progress
priority: P0
phase: scaffolding
tags: [foundation, scaffolding]
created: 2026-04-25
updated: 2026-04-26
---

## North-star outcome

Impact Crater has a versioned, public, well-organized foundation: a clean GitHub repo with a clear vision, a working four-level work-tracking system, two auto-running Claude Code skills that capture session state into the right docs, and a groomed roadmap with a locked MVP scope. Every subsequent session can pick up productively from `BOARD.md` without re-deriving context from chat history.

## Why now

Without the foundation, every later session burns time re-establishing context, decisions get lost, and novel ideas evaporate. This initiative is the prerequisite for every line of product code.

## Scope

- E-1.1 Repo scaffolding (✓ done)
- E-1.2 Vision grooming (✓ done — round 1)
- E-1.3 Architecture grooming
- E-1.4 Roadmap and MVP scoping
- E-1.5 Auto-merge policy (✓ done — adopted mid-flight 2026-04-26)

## Out of scope

- Any actual product code. Code lands during MVP work, after `E-1.4` closes the MVP scope.
- Tech-stack ADRs beyond the three already accepted at scaffolding (license, work-tracking, skills). The architecture-grooming epic produces the rest.

## Children

- E-1.1 — Repo scaffolding (done)
- E-1.2 — Vision grooming (done)
- E-1.3 — Architecture grooming (todo, ready — unblocked by E-1.2)
- E-1.4 — Roadmap and MVP scoping (todo, blocked by E-1.3)
- E-1.5 — Auto-merge policy (done — adopted mid-flight 2026-04-26)

## Linked decisions and ADRs

- ADR-0001 (license)
- ADR-0002 (work-tracking hierarchy)
- ADR-0003 (session-housekeeping skills — partially superseded by ADR-0004)
- ADR-0004 (auto-merge policy for skill and feature PRs)
- D-001 through D-005, D-006 through D-020 (E-1.2 round 1), D-021 (auto-merge policy)

## Activity log

- 2026-04-25 — created; status → in-progress
- 2026-04-26 — E-1.2 done (vision grooming round 1 closed: 15 D-NNN + 15 A-NNN + 7 N-NNN entries persisted via knowledge-curator PR; GROOMED_FEATURES populated; MVP partial-fill); E-1.3 now ready
- 2026-04-26 — E-1.5 created and closed in the same session per user directive *"PRs should be automerged"*; D-021 + ADR-0004 land the new policy; ADR-0003's "never auto-merge" clause partially superseded
