---
id: I-2
title: MVP — Story Video to YouTube
type: initiative
status: in-progress
priority: P0
phase: mvp
tags: [mvp, story-video, youtube]
created: 2026-05-03
updated: 2026-10-25
---

## North-star outcome

> *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes in a paragraph what kind of YouTube video they want and what kind of music, picks a target duration, and gets a publish-ready **Story Video** to their connected YouTube Studio account within 2–5 hours.*

(D-014 verbatim — the locked MVP success criterion.)

When this initiative closes, the user can run a real curation job from one of their own trips, refine the result if they want, click Approve, and have a Story Video on their YouTube channel within the documented wall-clock budget. The architecture is in place for v1 to add local-LLM routing, multi-platform publish, the live-job pattern, and reference-media style learning without rewriting MVP.

## Why now

E-1.1 (repo scaffolding), E-1.2 (vision grooming), E-1.3 (architecture grooming, 12 ADRs accepted), and E-1.4 round 1 (this round; MVP execution roadmap locked) are all done. Every architectural and product question that the MVP depends on has been answered. There is no remaining "we need to decide X first" — the next move is the first commit of code.

This initiative consumes the architecture cleanly: ADR-0005 (Python+FastAPI+React) is the foundation; ADR-0006 (storage) is the substrate; ADR-0007/0009 (LLM abstraction + cost-tiered routing) is the call layer; ADR-0010/0011/0012 (media + curation + music) is the pipeline; ADR-0013 (connector) is the publish path; ADR-0014 (orchestrator) is the agent harness; ADR-0015/0016 (resource accounting + privacy) is the cross-cutting layer. Each MVP epic implements specific stages of this stack.

## Scope

Thirteen epics: nine milestone epics (M0..M9 from MVP.md) plus four post-gate epics (E-2.10..E-2.13). The post-gate four are the rounds that followed the 2026-06-18 D-014 curate→preview pass — two feedback-driven curation-quality rounds on the real SW-US-trip job, the open-ended refinement layer, and the 2026-10-24 restart close-out — all still hardening the single Story Video rather than adding a v1 feature.

Milestone epics:

- **E-2.1 Scaffolding** (M0) — `pip install impact-crater` + CLI + FastAPI + React shell + first-time-setup wizard + SQLite schema
- **E-2.2 Headless curation through Stage 5** (M1) — `LLMClient` + Anthropic + Google + LLMRouter + telemetry + worker pool + pipeline Stages 1–5 working end-to-end without UI; ArcJudgment JSON output
- **E-2.3 Render + standard mode** (M2) — Stage 6 plan compile + Stage 7 ffmpeg render + standard music mode
- **E-2.4 UI MVP loop closed** (M3) — React UI for project creation, media drop, brief input, effort-level UX, in-job progress + cost live spend, preview UI with Approve / Refine buttons (Refine deferred to M6)
- **E-2.5 Music-video mode + section-to-media NL** (M4) — Madmom + librosa pipeline; tempo-aware beat-grid; A-013 NL section spec passed to Stage 5; cuts snap to beats
- **E-2.6 Person library + face recognition + privacy panel** (M5) — N-008 person library + reference collage + Stage 3 recognition integration; privacy panel UI; EXIF/GPS strip + face-blur paths; N-011 privacy-routing schema in place
- **E-2.7 Agentic refinement + orchestrator second-guess** (M6) — Stage 9 N-009 thinking step with 5 strategies; Stage 6 second-guess + user reconfirm UI; snapshot chain
- **E-2.8 YouTube publish** (M7) — `YouTubeConnector` with OAuth + resumable upload; publish UI with visibility selector; audit-log writer; full end-to-end demo
- **E-2.9 Cross-project user profile + polish + D-014 validation** (M8 + M9 rolled in) — feedback log + deterministic profile derivation + profile-driven suggestions on job creation; bug fixes + edge-case handling; D-014 success-criterion verified end-to-end on a real user dataset

Post-gate epics:

- **E-2.10 Feedback-driven curation quality** — coverage, balance, video share, specialness, trip cast, working inspect/feedback loop (from the SW-US-trip per-decision feedback)
- **E-2.11 Snappier, fuller edits + output polish + observability** — clip-duration caps, burst-montage, opt-in AI title card, music mood/section matching, job/phase-level feedback, richer live progress
- **E-2.12 Open-ended refinement layer + shared curation levers** — PlanDirective + destination reservation + the single-call refinement planner that re-renders child snapshots
- **E-2.13 Restart close-out + hygiene** — Phase 0 of the 2026-10-24 restart plan: tracker, docs, ADRs, feedback inbox and repo made true again; D-057 MVP-closure shape; zero spend

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

- E-2.1 — Scaffolding (done — 2026-05-03; M0; PRs #11/#12)
- E-2.2 — Headless curation through Stage 5 (done — 2026-05-04; M1; PR #13)
- E-2.3 — Render + standard mode (done — 2026-05-04; M2; PR #14)
- E-2.4 — UI MVP loop closed (done — 2026-05-05; M3; PR #15)
- E-2.5 — Music-video mode + section-to-media NL (done — 2026-05-05; M4; PR #16)
- E-2.6 — Person library + face recognition + privacy panel (done at MVP scope — 2026-05-05; M5; PR #17; privacy transforms, N-008 Stage-3 recognition and N-011 routing are unwired — see its Status section)
- E-2.7 — Agentic refinement + orchestrator second-guess (done — 2026-05-05; M6; PR #18; delivered epic-level, no stories; the shipped refine is E-2.12's single-call planner, the reconfirm UI was never built)
- E-2.8 — YouTube publish (done — 2026-05-05; M7; PR #19; delivered epic-level, no stories; connector + dry-run + audit writer only — in-app OAuth never built, zero publishes executed)
- E-2.9 — Cross-project user profile + polish + D-014 validation (in-progress — curate→preview half of D-014 passed 2026-06-18; closes on the first real YouTube publish in restart Phase 1)
- E-2.10 — Feedback-driven curation quality (done — 2026-07-01; PR #72; post-gate)
- E-2.11 — Snappier, fuller edits + output polish + observability (done — 2026-06-30; PR #67; post-gate)
- E-2.12 — Open-ended refinement layer + shared curation levers (done — 2026-07-01; PRs #72/#73; post-gate)
- E-2.13 — Restart close-out + hygiene (in-progress — Phase 0 of the restart plan, picked up 2026-10-24; mvp-hardening)

## Linked decisions and ADRs

All E-1.3 architecture ADRs (ADR-0005..0016) and all E-1.2/E-1.3 D-NNN entries (D-006..D-035) are load-bearing for this initiative. The execution-roadmap decisions specifically:

- D-014 — MVP success criterion (the north-star outcome above, verbatim)
- D-036 — MVP execution roadmap = 9 milestones with AI-assisted full-time velocity
- D-037 — Keep all E-1.3 MVP scope expansions
- D-038 — Code-org sequencing (vertical-slice-early + backend-before-frontend-per-milestone + inline-tests)

## Activity log

- 2026-05-03 — created (E-1.4 round 1 closure). Status `backlog` until E-1.4 closes (round 2 ROADMAP.md lock still pending), at which point the first epic (E-2.1 Scaffolding) becomes ready and I-2 promotes to `in-progress`.
- 2026-05-03 — **promoted from `backlog` → `in-progress`** following E-1.4 round 2 closure (E-1.4 done; I-1 done; scaffolding-phase exit). E-2.1 (Scaffolding M0) is the first ready epic = first commit of code in the next session.
- 2026-05-03 — E-2.1 (M0) picked up; 6 stories created (S-2.1.1..6). **First commit of actual application code in this session.**
- 2026-05-03 — **E-2.1 done.** All 6 stories closed; ~50 files of application code on master (Python backend + Vite/TS/Tailwind frontend + 12-table SQLite schema + 6-step setup wizard end-to-end + cross-OS dev launchers + 10-step smoke-test doc). E-2.2 (Headless curation through Stage 5; M1) is now Up Next.
- 2026-05-04 — E-2.2 (M1) picked up. 8 stories created (S-2.2.1..8). M0 verified end-to-end on Windows (PR #12); cross-OS verification still falls to user via `docs/dev/M0-SMOKE-TEST.md`. M1 brings the LLM stack online + pipeline Stages 1-5; real-API integration tests gated behind `--integration` marker.
- 2026-05-04 — **E-2.2 done.** All 8 stories closed in one session. The full headless pipeline (ingest → bulk ops → rich metadata → pre-filter → narrative-arc judgment) returns a structured ArcJudgment via `POST /api/jobs/headless` in ~19s on a 4-photo real-API smoke test. 139/139 tests green. **E-2.3 (M2 render + standard mode) is now Up Next.**
- 2026-05-04 — **E-2.3 done.** All 4 stories closed in the same session. The full M2 pipeline (Stages 1-7) returns a rendered MP4 via `POST /api/jobs/render` against real Anthropic Opus + Google Flash + ffmpeg in ~22s on a 3-photo + 4s-tone smoke test. ffmpeg 8.1 installed via winget on dev. 169/169 tests green. **E-2.4 (M3 UI MVP loop closed) is now Up Next.**
- 2026-05-05 — **E-2.4 done.** All 5 stories closed. The full UI loop (Wizard → Dashboard → New Project → Effort+Cost → In-Progress → Preview) is wired against an async-jobs API with WebSocket progress events. Settings panel ships in the same epic. M3 also piggybacked an M1 follow-up: per-call LLMCallEvent telemetry + ProgressSink in the router, so JobCostSummary actually populates and the live-spend panel updates in real time. **218 tests green** (185 backend unit + 26 frontend unit + 7 backend integration). **E-2.5 (M4 music-video) and E-2.6 (M5 person library + privacy) are now Up Next — parallelizable.**
- 2026-10-24 — **Restart audit** (docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md). After ~4 idle months: the curate→preview half of D-014 stands (1,663 assets, 60 min warm after a 2h55m cold run, ~$50 total); the publish half has never executed (audit table 0 rows; in-app OAuth never built; dry-run default). E-2.13 filed as Phase 0 (honest close-out + hygiene) and S-2.10.9 (model-lineup bump) as the first Phase 1 story. I-2 stays in-progress until S-2.13.2 records D-057 and Phase 1 lands the real publish. Children list is stale (rewritten in S-2.13.1).
- 2026-10-24 — S-2.13.1 (tracker reconciliation, per the restart audit): Children rewritten to exactly E-2.1..E-2.13 with status and done date from each epic file and git (the old list carried duplicate E-2.4/E-2.5/E-2.6 lines and pre-M4 "blocked by" states; E-2.5–E-2.8 went done 2026-05-05 in PRs #16–#19, E-2.10 is marked done 2026-07-01 in the same reconciliation, E-2.11 done 2026-06-30, E-2.12 done 2026-07-01, E-2.13 in-progress). Scope reworded from "nine epics" to thirteen (nine milestone + four post-gate). Status unchanged: in-progress until the first real publish closes E-2.9.
- 2026-10-25 — D-057 recorded (S-2.13.2): the MVP closes on the amended `docs/roadmap/MVP.md` pre-flight once the first real private YouTube publish lands (restart Phase 1); that publish closes E-2.9 and I-2 together, at which point S-2.9.17 / S-2.9.18 / S-2.9.19 move to E-3.11. The other pre-flight items are re-scoped with tracker IDs and no longer hold the MVP open.
