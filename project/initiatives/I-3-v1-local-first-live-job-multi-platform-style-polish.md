---
id: I-3
title: v1 — Local-first + live job + multi-platform + style + polish
type: initiative
status: in-progress
priority: P1
phase: v1
tags: [v1]
created: 2026-06-14
updated: 2026-10-24
---

## North-star outcome

The app is the differentiated product: it runs local-first on capable hardware, ingests media live during an event, publishes to Instagram/Facebook/X as well as YouTube, learns the user's style from reference media, and ships the power-user polish bundle.

## Why now

MVP proved the single thin slice; v1 turns it into something materially better than generic AI media tools, leading with the highest-novelty differentiators (local-first, live job, style learning) per D-039. The 2026-10-24 restart audit re-sequences how v1 is reached: the hardening the MVP still owes (CI, mid-job spend guard, API hardening, packaging, eval harness, disk hygiene) is hosted here at `mvp-hardening` phase so I-2 can close on the first real publish (D-057), then v1 opens publish-and-artifact-first (Phase 4: E-3.3 → E-3.5 → E-3.8 → E-3.7 → E-3.9 → E-3.4/E-3.6 remainder), local-first follows in Phase 5 (E-3.1), and the live job (E-3.2) waits for the Trip Package gate in Phase 6. Every deviation from D-039's v1.1–v1.9 order is recorded as a D-NNN, as D-039 requires.

## Scope

Local-first LLM; live job; multi-platform connectors; reference-style learning; power-user polish; auto editing; music sourcing expansion; LLM-driven profile; full cache — plus, ahead of the formal v1 opening: a quality eval harness + golden set (E-3.10) and the restart Phases 1–2 hardening + release engineering (E-3.11).

## Out of scope

Mobile, multi-agent, conversational refinement at scale, generated music, the Trip Package and crowd removal (I-4); hosted multi-tenant mode (I-5). The first real publish and the MVP closure itself stay under I-2 (E-2.8 / E-2.9 / E-2.13).

## Children

- E-3.1 — Local-first LLM runtime + operation-aware router (todo; Phase 5, with Phase 2/3 pieces)
- E-3.2 — Live job: continuous ingest + multi-output orchestration (todo; Phase 6, behind the gate)
- E-3.3 — Multi-platform connectors: Instagram + Facebook + X (in-progress — YouTube/Instagram/Facebook connectors landed dry-run-only in PR #34, 2026-05-11; Phase 1 Connect-in-Settings, Phase 4 live posts)
- E-3.4 — Reference-media style learning (todo; Phase 4 stretch)
- E-3.5 — Power-user polish bundle (todo; Phase 3/4)
- E-3.6 — Auto photo / video editing (todo; Phase 3)
- E-3.7 — Music sourcing expansion (todo; Phase 4)
- E-3.8 — LLM-driven profile re-derivation (todo; Phase 2 emitters, Phase 4 UI)
- E-3.9 — Cross-job cache: full reuse-class semantics (todo; Phase 2 hygiene + delete, Phase 3 pre-filter, Phase 4 classes)
- E-3.10 — Quality eval harness + golden set (todo; mvp-hardening; Phase 2)
- E-3.11 — Restart Phases 1–2 hardening + release engineering (todo; mvp-hardening; Phases 1–2)

## Linked decisions and ADRs

- ROADMAP.md §v1, D-039 (v1 order; re-sequencing needs a superseding D-NNN), D-042 (gate that holds E-3.2 / the package), D-057 (pending — MVP closure shape and why mvp-hardening epics sit here)
- A-027, A-029 (filed 2026-10-24; realised by E-3.9 / E-3.10)
- `docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md` §4.3 F (#34, #35), §5 Phases 1–5

## Activity log

- 2026-06-14 — created (roadmap backfill so the in-app workplan tracker shows the full plan; A-024 follow-up)
- 2026-10-24 — reconciled in S-2.13.1 from the restart audit (docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md). The restart plan re-sequences v1: hardening the MVP still owes is hosted here as E-3.10 (eval harness + golden set) and E-3.11 (Phases 1–2 hardening + release engineering), both `mvp-hardening`, so that I-2 can close on the first real publish; v1 then opens publish-and-artifact-first (Phase 4), local-first in Phase 5, live job in Phase 6 — D-057 is to record this (S-2.13.2) and a Phase 4 D-NNN formally opens I-3 re-sequenced, superseding D-039's v1.1–v1.9 order. Children list given titles and phases; E-3.3 corrected to in-progress (connectors landed 2026-05-11, PR #34). Status deliberately stays `backlog` although E-3.3 is in-progress: the README's "promotes when its first epic is picked up" rule is not applied here because the plan makes the opening of v1 an explicit decision (§4.3 #34); the audit records that the 2026-06-14 backfill reversed D-039's clause without one.
- 2026-10-24 — status backlog → in-progress (S-2.13.1): E-3.3 is in-progress (connectors landed in PR #34) and E-3.10 / E-3.11 host restart Phases 1–3 here, so the README rule (an initiative promotes when its first epic is picked up) applies. The formal opening of the v1 feature epics (E-3.1, E-3.2, E-3.4–E-3.9 beyond their hardening children) is still the Phase 4 D-NNN that D-057 names; until then this initiative is in-progress for hardening only.
