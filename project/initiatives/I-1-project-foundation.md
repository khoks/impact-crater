---
id: I-1
title: Project foundation
type: initiative
status: in-progress
priority: P0
phase: scaffolding
tags: [foundation, scaffolding]
created: 2026-04-25
updated: 2026-04-28
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
- E-1.3 — Architecture grooming (in-progress — round 1 foundation + LLM stack)
- E-1.4 — Roadmap and MVP scoping (todo, blocked by E-1.3)
- E-1.5 — Auto-merge policy (done — adopted mid-flight 2026-04-26)

## Linked decisions and ADRs

- ADR-0001 (license)
- ADR-0002 (work-tracking hierarchy)
- ADR-0003 (session-housekeeping skills — partially superseded by ADR-0004)
- ADR-0004 (auto-merge policy for skill and feature PRs)
- D-001 through D-005, D-006 through D-020 (E-1.2 round 1), D-021 (auto-merge policy), D-022 (E-1.2 round 2: refine-loop UX redirect)

## Activity log

- 2026-04-25 — created; status → in-progress
- 2026-04-26 — E-1.2 done (vision grooming round 1 closed: 15 D-NNN + 15 A-NNN + 7 N-NNN entries persisted via knowledge-curator PR; GROOMED_FEATURES populated; MVP partial-fill); E-1.3 now ready
- 2026-04-26 — E-1.5 created and closed in the same session per user directive *"PRs should be automerged"*; D-021 + ADR-0004 land the new policy; ADR-0003's "never auto-merge" clause partially superseded
- 2026-04-26 — same-day refinement to E-1.5: branch-protection on master required a review, blocking the auto-merge step. User chose to pin `--admin` in the standing merge command. ADR-0004 gained a "Branch-protection compatibility" section; SKILL.md files, hook, and CLAUDE.md updated accordingly. E-1.5 stays `done`.
- 2026-04-28 — E-1.2 round-2 redirect (post-closure): user redirected the refine-loop UX entry point. D-022 filed superseding the refine-loop half of D-020; refine is now offered alongside Approve at the post-render moment, not toggled at job creation. GROOMED_FEATURES.md + MVP.md + T-1.2.1.4 / S-1.2.1 / E-1.2 activity logs updated. User reaffirmed N-001..N-007 OK on public master, no patent-priority hold. E-1.2 remains `done` (this is an append-only post-closure tightening, not new scope); E-1.3 still Up Next.
- 2026-04-28 — E-1.3 picked up; status → in-progress for E-1.3 (initiative I-1 already in-progress). Round-1 Story S-1.3.1 + 5 Tasks (T-1.3.1.1..5) created, scoping foundation + LLM stack ADRs (ADR-0005..0009).
- 2026-04-28 — E-1.3 round 1 closed: ADR-0005..0009 + D-023..D-027 filed; ARCHITECTURE.md refreshed; S-1.3.1 + T-1.3.1.1..5 marked done. E-1.3 stays in-progress for rounds 2 + 3 (media + curation; connectors + harness + cross-cutting).
- 2026-05-02 — E-1.3 round 2 picked up; S-1.3.2 + T-1.3.2.1..3 created scoping ADR-0010 media pipeline + ADR-0011 curation engine + ADR-0012 music alignment. Two new novel mechanisms surfaced (N-008 person-library + reference-collage face recognition; N-009 agentic refinement with custom plan generation) and one MVP scope expansion (A-013 section-to-media NL mapping reclassified v1 → MVP).
