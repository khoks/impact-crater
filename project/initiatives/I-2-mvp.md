---
id: I-2
title: MVP — Story Video to YouTube
type: initiative
status: backlog
priority: P0
phase: mvp
tags: [mvp, story-video, youtube]
created: 2026-05-03
updated: 2026-05-03
---

## North-star outcome

> *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes in a paragraph what kind of YouTube video they want and what kind of music, picks a target duration, and gets a publish-ready **Story Video** to their connected YouTube Studio account within 2–5 hours.*

(D-014 verbatim — the locked MVP success criterion.)

When this initiative closes, the user can run a real curation job from one of their own trips, refine the result if they want, click Approve, and have a Story Video on their YouTube channel within the documented wall-clock budget. The architecture is in place for v1 to add local-LLM routing, multi-platform publish, the live-job pattern, and reference-media style learning without rewriting MVP.

## Why now

E-1.1 (repo scaffolding), E-1.2 (vision grooming), E-1.3 (architecture grooming, 12 ADRs accepted), and E-1.4 round 1 (this round; MVP execution roadmap locked) are all done. Every architectural and product question that the MVP depends on has been answered. There is no remaining "we need to decide X first" — the next move is the first commit of code.

This initiative consumes the architecture cleanly: ADR-0005 (Python+FastAPI+React) is the foundation; ADR-0006 (storage) is the substrate; ADR-0007/0009 (LLM abstraction + cost-tiered routing) is the call layer; ADR-0010/0011/0012 (media + curation + music) is the pipeline; ADR-0013 (connector) is the publish path; ADR-0014 (orchestrator) is the agent harness; ADR-0015/0016 (resource accounting + privacy) is the cross-cutting layer. Each MVP epic implements specific stages of this stack.

## Scope

Nine epics, one per milestone (M0..M9 from MVP.md):

- **E-2.1 Scaffolding** (M0) — `pip install impact-crater` + CLI + FastAPI + React shell + first-time-setup wizard + SQLite schema
- **E-2.2 Headless curation through Stage 5** (M1) — `LLMClient` + Anthropic + Google + LLMRouter + telemetry + worker pool + pipeline Stages 1–5 working end-to-end without UI; ArcJudgment JSON output
- **E-2.3 Render + standard mode** (M2) — Stage 6 plan compile + Stage 7 ffmpeg render + standard music mode
- **E-2.4 UI MVP loop closed** (M3) — React UI for project creation, media drop, brief input, effort-level UX, in-job progress + cost live spend, preview UI with Approve / Refine buttons (Refine deferred to M6)
- **E-2.5 Music-video mode + section-to-media NL** (M4) — Madmom + librosa pipeline; tempo-aware beat-grid; A-013 NL section spec passed to Stage 5; cuts snap to beats
- **E-2.6 Person library + face recognition + privacy panel** (M5) — N-008 person library + reference collage + Stage 3 recognition integration; privacy panel UI; EXIF/GPS strip + face-blur paths; N-011 privacy-routing schema in place
- **E-2.7 Agentic refinement + orchestrator second-guess** (M6) — Stage 9 N-009 thinking step with 5 strategies; Stage 6 second-guess + user reconfirm UI; snapshot chain
- **E-2.8 YouTube publish** (M7) — `YouTubeConnector` with OAuth + resumable upload; publish UI with visibility selector; audit-log writer; full end-to-end demo
- **E-2.9 Cross-project user profile + polish + D-014 validation** (M8 + M9 rolled in) — feedback log + deterministic profile derivation + profile-driven suggestions on job creation; bug fixes + edge-case handling; D-014 success-criterion verified end-to-end on a real user dataset

## Out of scope

Anything explicitly tagged out-of-MVP in [`docs/roadmap/MVP.md`](../../docs/roadmap/MVP.md) and [`docs/vision/GROOMED_FEATURES.md`](../../docs/vision/GROOMED_FEATURES.md). Specifically:

- Multiple artifact types in one project (only Story Video at MVP per D-006).
- Multiple platforms in one publish (only YouTube at MVP per D-007).
- Local-first LLM routing (v1 — D-016; the abstraction is in place at MVP per ADR-0008).
- The N-002 operation-aware router (v1 — N-002).
- The full N-010 LLM-driven profile re-derivation (deterministic-only at MVP per E-2.9; LLM derivation post-launch).
- The N-011 privacy-routing local destination (v1 — local-LLM lands first; the routing-config schema is in place at MVP per E-2.6).
- Live-job pattern (v1 — A-012 / N-005).
- Reference-media style learning (v1 — A-014 / N-004).
- Multi-version artifact comparison (v1 — A-006).
- Quality floor calibration + user override (v1 — A-007).
- Watermark / brand-mark mode (v1 — A-008).
- Royalty-free music starter pack + licensed-library integration (v1 — D-018).
- Auto photo / video editing (v1).
- Mobile UI (v2 — D-019).
- Multi-agent harness (v2 — D-017).
- Conversational refinement at scale (v2).
- Generated music (v2 — D-018).
- Hosted-service mode (v3 — CLAUDE.md mission).

## Children

- E-2.1 — Scaffolding (todo, ready — unblocked by I-1's E-1.4 closure)
- E-2.2 — Headless curation through Stage 5 (todo, blocked by E-2.1)
- E-2.3 — Render + standard mode (todo, blocked by E-2.2)
- E-2.4 — UI MVP loop closed (todo, blocked by E-2.3)
- E-2.5 — Music-video mode + section-to-media NL (todo, blocked by E-2.4)
- E-2.6 — Person library + face recognition + privacy panel (todo, blocked by E-2.4)
- E-2.7 — Agentic refinement + orchestrator second-guess (todo, blocked by E-2.4 + E-2.6)
- E-2.8 — YouTube publish (todo, blocked by E-2.3)
- E-2.9 — Cross-project user profile + polish + D-014 validation (todo, blocked by all of E-2.1..E-2.8)

## Linked decisions and ADRs

All E-1.3 architecture ADRs (ADR-0005..0016) and all E-1.2/E-1.3 D-NNN entries (D-006..D-035) are load-bearing for this initiative. The execution-roadmap decisions specifically:

- D-014 — MVP success criterion (the north-star outcome above, verbatim)
- D-036 — MVP execution roadmap = 9 milestones with AI-assisted full-time velocity
- D-037 — Keep all E-1.3 MVP scope expansions
- D-038 — Code-org sequencing (vertical-slice-early + backend-before-frontend-per-milestone + inline-tests)

## Activity log

- 2026-05-03 — created (E-1.4 round 1 closure). Status `backlog` until E-1.4 closes (round 2 ROADMAP.md lock still pending), at which point the first epic (E-2.1 Scaffolding) becomes ready and I-2 promotes to `in-progress`.
