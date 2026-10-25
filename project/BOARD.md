# Board

> **Last updated:** 2026-10-24 — **Phase 0 session 1: hygiene (S-2.13.6, PR #77) + tracker reconciliation (S-2.13.1).** Every table below is now **generated from frontmatter** by `scripts/tracker_board.py` (`--check` fails on drift; the status tally sits at the bottom). What changed: E-2.10 closed (2026-07-01, PR #72) once S-2.10.8 moved to E-3.1 and S-2.10.4 / S-2.10.9 to the new **E-3.11** (restart Phases 1–2 hardening + release engineering); **E-3.10** (quality eval harness + golden set, A-029) and **E-4.6** (AI crowd removal, hosting S-2.9.7) filed; 20 new stories groomed for the restart plan (S-3.3.4–7, S-3.5.5–7, S-3.2.5, S-3.1.4–5, S-3.8.3, S-3.9.3–4, S-3.10.1–3, S-3.11.1–5); I-2 Children = E-2.1..E-2.13; E-2.9 lists all 17 remaining children; E-2.5/E-2.6 Children filled, E-2.7/E-2.8 marked delivered epic-level, E-2.6 relabelled done-at-MVP-scope; S-3.3.1 (Instagram) and S-3.3.2 (Facebook) done — env-var credentials, dry-run only, never live-tested — and E-3.3 → in-progress, so **I-3 → in-progress** (hardening only; the v1 feature epics open on the Phase 4 D-NNN per D-057); S-2.6.4 canceled (→ S-3.1.3), S-2.6.2 re-homed to E-3.1 with its false ticks removed; S-2.9.17 re-scoped to the HTTP Range check; S-2.9.19 promoted to mvp-hardening P1; S-2.9.4 → E-3.6, S-2.9.15 → E-3.9. **Vocabulary now defined in `project/README.md`:** `deferred`, `backlog` (initiatives only), `ready` is not a status, the `mvp-hardening` phase (E-2.10/11/12 and their stories retagged, per D-057), child-inherits-epic-phase, `plan-phase-N` tags, and the four acceptance-box annotations (every unchecked box on a done item now says `verified by` / `deferred →` / `superseded by` / `unverified`). Feedback triage (S-2.13.3), D-057 + MVP.md (S-2.13.2) and the public-trust docs pass (S-2.13.4) follow in this session; the ADR truth bundle (S-2.13.5) and dead-code sweep (S-2.13.7) are queued for session 2.
> **Earlier (2026-10-24, restart audit):** **Restart audit + 7-phase plan (docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md).** First session after a ~4-month pause. An 8-dimension audit (tracker, hygiene, code-vs-claims, vision/future, decisions, testing, usability, done-inventory), each adversarially verified, found: the single-video journey is wired end to end and the curate→preview half of D-014 stands (1,663 assets; 60 min warm resume after a 2h55m cold run that died on credit exhaustion; ~$50 total), but **no publish has ever executed** (audit 0 rows; in-app OAuth never built; dry-run default), the profile / person library / privacy toggles / effort levels / second-guess are **built but inert**, the job registry is in-memory (three 900+ media jobs lost on 2026-06-30), routing pins **Claude 4.x IDs** that may be retired, `~/.impact-crater/projects` is **92 GB** from per-project scene caches, 11 feedback items are still `new`, and the tracker/docs overstate delivery. Backend 476 pass / 7 skipped, frontend 38 vitest + tsc green today. **Filed:** E-2.13 (Phase 0: honest close-out + hygiene, 8 stories) and S-2.10.9 (model-lineup bump, first Phase 1 story). **Known drift left for S-2.13.1 on purpose (one reconciliation PR):** E-2.10 frontmatter in-progress vs the Recently Done row below; I-2/E-2.9 Children lists stale; S-2.6.2/S-2.6.4 false ticks; S-3.3.1/S-3.3.2 todo though IG/FB connectors landed in PR #34; S-2.9.17 premise false. The rows below were corrected only where frontmatter already contradicted them (S-2.10.5/6/7 removed from Up Next / Backlog; duplicate S-2.10.8 row removed). **Knowledge swept:** A-027, A-028, A-029; landscape doc merged in PR #75.
> **Earlier (2026-07-01):** **Open-ended refinement + shared curation levers shipped (E-2.12, D-056).** From "pick up S-2.10.4/5/6/7/8 + S-2.11.5/6 and make refinement handle arbitrary NL requests": built two shared levers — **PlanDirective** (ADR-0019: duration/positional/tempo shaping Stage 6 consumes + refinement emits) and **ReservationSet** (S-2.10.5: source-agnostic must-keep through Stage 4 = the **Vegas fix**) — then the **agentic refinement loop** (S-2.12.3) whose tools are thin wrappers over them (pacing → re-run Stage 6 only; coverage → re-Stage-4 + re-judge; content → re-judge; renders a child snapshot). Plus **S-2.10.4** cast merge-pass, **S-2.10.6** capture-day stratified budget (A/B-gated), **S-2.10.7** model bump (Opus 4.8 / Sonnet 4.6, incl. the Opus-4.8-drops-`temperature` fix), **S-2.10.8** pluggable local-embedder interface (stub; weights deferred), **S-2.11.5b** title-card cost line-item. Backend **464 pass**; frontend typecheck + 38 vitest green. **Verified live**: both a pacing refinement ("beginning clips 50% longer, shrink the photos around them") and a coverage refinement ("don't drop the Zion shots, lean on landscapes") were interpreted → the right lever → re-rendered a child snapshot end-to-end. ADR-0019/0020; **knowledge swept:** D-056. **Op note:** restart the detached dev server after backend commits before UI-testing.
> **Earlier (2026-06-30):** **AI-written splash-card title shipped (S-2.11.7, [PR #69](https://github.com/khoks/impact-crater/pull/69), D-055).** P3 polish follow-up to S-2.11.5: when the user doesn't type a `title_text`, the opt-in title card's auto-derived title now comes from a cheap Tier-S `generate_title_text` op (brief + modal year → clean 2–5 word title, place-name typo-fixing) that **reuses the structured-text primitive** (`parse_user_brief` + `{title}` schema) rather than widening the `LLMClient` protocol; the old first-clause heuristic is kept as the fail-soft fallback, and an explicit `title_text` short-circuits the call. **Knowledge swept:** D-055, A-026.
> **Earlier (2026-06-30):** **Round-2 output-feedback pass shipped (E-2.11, [PR #67](https://github.com/khoks/impact-crater/pull/67), D-054).** From the user's 10-point round-2 feedback on the SW-US re-renders, delivered all of E-2.11 on the "do all" instruction: **S-2.11.1** snappier/fuller edits (per-clip duration band photos 1–3s / video ≥2s, coverage of every location+time) + **T-2.11.1.6** candidate-level ≤4/viewpoint cap; **S-2.11.2** job- and phase-level feedback; **S-2.11.3** richer live progress (per-stage sub-module chips); **S-2.11.4** burst-montage clip type (dense same-backdrop bursts → one ~0.5s-per-member sequence); **S-2.11.5** opt-in AI title/splash card (remote image-gen + cast faces + title/year, fail-soft); **S-2.11.6** music mood/section matching (both modes). Backend suite **419 pass**; verified via reconstruction render (title card + 44-clip/115s snappy arc) and **live through the app UI** (toggle, three feedback levels, sub-module progress chips, a full job submitted → rendered opening on the AI title card). Also marked **S-2.10.1/2/3 done** (shipped + output-verified). **Op note:** a long-running detached dev server serves stale Python modules — restart it after backend commits before UI-testing new server-side behaviour. **Knowledge swept:** D-054.
> **Earlier (2026-06-29):** **Feedback-driven curation-quality pass (E-2.10).** Inspected the D-014 SW-US-trip job (snapshot b4b73c7b1fe044b7) against its media, submitted 8 per-decision feedback items via the in-app loop, and from them shipped: **S-2.10.1** (fix the feedback-modal hang + video scene thumbnails + drop-card scores), **S-2.10.2** (specialness-aware Stage 4: 4-term score + quality-floor rescue + tie-breaks), **S-2.10.3** (Stage 5 video-share/variety/balance + chronological opener + MOTION/STILL candidate tags) — all tested (401 backend pass, frontend typechecks) on a feature branch pending the user's live-output verification. Partial: **S-2.10.4** (cast conjunctive group gate landed; merge-pass/detection pending). Filed for next: **S-2.10.5** (named-destination coverage — the real Vegas fix, P0), **S-2.10.6** (capture-day stratified budget), **S-2.10.7** (model bump Opus 4.8/Sonnet 4.6), **S-2.10.8** (local CLIP/SigLIP embedder). Resolved **S-2.9.20** (Vegas root cause = no brief-aware coverage → S-2.10.5). **Knowledge swept:** ADR-0017, ADR-0018, D-053.
> **Earlier (2026-06-18):** **MVP D-014 validation PASSED + cost/UX hardening.** The user ran a real **1,663-asset SW-US-trip job** (1,481 photos + 182 videos → 2,067 shots) end-to-end → a publish-ready **108s Story Video at confidence 0.85**, evaluated good against the brief — **the D-014 MVP gate is met**. This session also shipped **S-2.9.13** (1-click positioning realign across 9 docs + the app UI + RAW_VISION addenda, D-050), **S-2.9.14** (token-accurate cost metering after a ~5× undercount + credit-exhausted error surfacing + accurate Stage-2 progress; daily cap $50→$100; D-048), and **S-2.9.16** (snapshot-keyed Inspect & Feedback so finished jobs stay reviewable after a restart). Filed: **S-2.9.15** (two-phase pre-filter, D-049), **S-2.9.17** (faststart render), **S-2.9.18** (token-aware pre-job estimate), **S-2.9.19** (persist job registry, A-025), **S-2.9.20** (Las Vegas absent from curation). GitHub Pages docs site + branding live (D-052). **Knowledge swept:** D-048..D-052 + A-025 logged.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase | Status |
|---|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp | in-progress |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project user profile (N-010 minimum-viable) + polish + D-014 validation | Epic | P0 | mvp | in-progress |
| [E-2.13](./epics/E-2.13-restart-close-out-and-hygiene.md) | Restart close-out + hygiene (Phase 0 of the 2026-10-24 plan) (plan-phase-0) | Epic | P0 | mvp-hardening | in-progress |
| [S-2.13.8](./stories/S-2.13.8-owner-model-availability-check-and-spend-envelope.md) | Owner-side $0 check: which Claude / Gemini model IDs still resolve; pick targets and the Phase 1 spend envelope (plan-phase-0) | Story | P0 | mvp-hardening | in-progress |
| [I-3](./initiatives/I-3-v1-local-first-live-job-multi-platform-style-polish.md) | v1 — Local-first + live job + multi-platform + style + polish | Initiative | P1 | v1 | in-progress |
| [E-3.3](./epics/E-3.3-multi-platform-connectors-instagram-facebook-x.md) | Multi-platform connectors — Instagram + Facebook + X (plan-phase-1, plan-phase-4) | Epic | P1 | v1 | in-progress |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase | Status |
|---|---|---|---|---|---|
| [E-3.10](./epics/E-3.10-quality-eval-harness-and-golden-set.md) | Quality eval harness + golden set (plan-phase-2) | Epic | P0 | mvp-hardening | todo |
| [E-3.11](./epics/E-3.11-restart-hardening-and-release-engineering.md) | Restart Phases 1–2 hardening + release engineering (plan-phase-1, plan-phase-2) | Epic | P0 | mvp-hardening | todo |
| [S-2.10.9](./stories/S-2.10.9-model-lineup-bump-current-ga-ids.md) | Model-lineup bump to current GA IDs — pinned model_version, rate cards, data-driven temperature guard, model-not-found mapping, real key ping (plan-phase-1) | Story | P0 | mvp-hardening | todo |
| [S-3.3.5](./stories/S-3.3.5-connect-youtube-in-settings.md) | Connect YouTube in Settings (loopback OAuth → connector_credentials) (plan-phase-1) | Story | P0 | v1 | todo |
| [S-3.10.1](./stories/S-3.10.1-eval-plan-script-and-thresholds.md) | scripts/eval_plan.py + D-058 thresholds on frozen SW-US and Zion fixtures (pytest -m eval) (plan-phase-2) | Story | P0 | mvp-hardening | todo |
| [S-3.11.2](./stories/S-3.11.2-test-ci.md) | Test CI — ruff / mypy / pytest / vitest / build / mkdocs on ubuntu and windows; branch protection; ADR-0004 --admin → --auto (plan-phase-1) | Story | P0 | mvp-hardening | todo |
| [E-3.5](./epics/E-3.5-power-user-polish-bundle.md) | Power-user + polish bundle (plan-phase-1, plan-phase-2, plan-phase-3) | Epic | P1 | v1 | todo |
| [S-2.9.19](./stories/S-2.9.19-persist-job-registry-survive-restart.md) | Persist the job registry so live/preview views survive a restart (plan-phase-2) | Story | P1 | mvp-hardening | todo |
| [S-2.13.5](./stories/S-2.13.5-adr-truth-bundle-and-governance-files.md) | ADR truth bundle (ADR-0007/0009/0010/0012/0013/0018/0020 + ADR-0021) and repo governance files (plan-phase-0) | Story | P1 | mvp-hardening | todo |
| [S-3.5.5](./stories/S-3.5.5-refine-as-job-and-publish-from-any-snapshot.md) | Refine as a job + publish from any snapshot (SnapshotInspect canonical preview) (plan-phase-1, plan-phase-2) | Story | P1 | v1 | todo |
| [S-3.10.2](./stories/S-3.10.2-golden-set-from-feedback.md) | Golden set — export the owner's decision-level feedback verdicts; harness reports agreement (plan-phase-2) | Story | P1 | mvp-hardening | todo |
| [S-3.11.1](./stories/S-3.11.1-mid-job-quota-guard.md) | Mid-job quota guard — check before every paid call (total + per-provider), refinement and title card included, UTC day boundary (plan-phase-2) | Story | P1 | mvp-hardening | todo |
| [S-3.11.3](./stories/S-3.11.3-local-api-hardening.md) | Local API hardening — per-install bearer token, WS origin check, refuse non-loopback --host without --allow-remote, SECURITY.md (plan-phase-1) | Story | P1 | mvp-hardening | todo |
| [S-3.11.6](./stories/S-3.11.6-clear-ruff-mypy-baseline-debt.md) | Clear the ruff / mypy baseline debt so CI can enforce them (plan-phase-1) | Story | P1 | mvp-hardening | todo |
| [S-2.9.18](./stories/S-2.9.18-token-aware-pre-job-cost-estimate.md) | Token-aware pre-job cost estimate (align the preview with the now-accurate meter) (plan-phase-2) | Story | P2 | mvp-hardening | todo |
| [S-2.10.4](./stories/S-2.10.4-trip-cast-group-crowd-tightening.md) | Trip-cast group/crowd tightening (appearance/day gate + merge + detection) (plan-phase-2) | Story | P2 | mvp-hardening | todo |
| [S-2.13.7](./stories/S-2.13.7-dead-code-sweep.md) | Dead-code sweep — placeholder router, six unimplemented routed ops, unused events and client methods (plan-phase-0) | Story | P2 | mvp-hardening | todo |
| [S-3.10.3](./stories/S-3.10.3-cap-violation-counters.md) | Cap-violation counters in diagnostics.json — instrument before the D-053 repair-loop decision (plan-phase-2) | Story | P2 | mvp-hardening | todo |
| [S-3.11.4](./stories/S-3.11.4-wheel-packaging-prompts-and-config.md) | Wheel packaging of prompts/ and config/; requires-python 3.12; single version source; CHANGELOG (plan-phase-2) | Story | P2 | mvp-hardening | todo |
| [S-3.11.5](./stories/S-3.11.5-frontend-dependency-bump.md) | Frontend dependency bump — vite / vitest / jsdom / @types/node / tailwind / react-router majors; clear npm audit; engines check (plan-phase-1) | Story | P2 | mvp-hardening | todo |
| [S-2.9.17](./stories/S-2.9.17-faststart-render-instant-preview.md) | Inline preview shows the first frame promptly — verify HTTP Range support for render.mp4 on starlette 1.0 (plan-phase-2) | Story | P3 | mvp-hardening | todo |

## Backlog (queued)

| ID | Title | Type | Priority | Phase | Status |
|---|---|---|---|---|---|
| [S-2.6.2](./stories/S-2.6.2-stage3-n008-integration.md) | Stage 3 N-008 integration — collage as 2nd image input (plan-phase-3) | Story | P0 | v1 | deferred |
| [E-3.1](./epics/E-3.1-local-first-llm-runtime-operation-aware-router.md) | Local-first LLM runtime + operation-aware router (plan-phase-2, plan-phase-3, plan-phase-5) | Epic | P1 | v1 | todo |
| [E-3.6](./epics/E-3.6-auto-photo-video-editing.md) | Auto photo / video editing (plan-phase-3) | Epic | P1 | v1 | todo |
| [E-3.8](./epics/E-3.8-llm-driven-profile-re-derivation.md) | LLM-driven profile re-derivation (plan-phase-2, plan-phase-4) | Epic | P1 | v1 | todo |
| [E-3.9](./epics/E-3.9-cross-job-cache-full-reuse-class-semantics.md) | Cross-job cache — full reuse-class semantics (plan-phase-2, plan-phase-3) | Epic | P1 | v1 | todo |
| [S-2.10.8](./stories/S-2.10.8-local-image-embedder.md) | Local CLIP/SigLIP image embedder replacing caption-then-embed (plan-phase-3) | Story | P1 | v1 | todo |
| [S-3.1.4](./stories/S-3.1.4-privacy-honesty-minimum.md) | Privacy honesty minimum — explicit strip-EXIF, never send originals, truthful "What we send to the AI" copy (plan-phase-2) | Story | P1 | v1 | todo |
| [S-3.9.3](./stories/S-3.9.3-shared-scene-cache-and-disk-accounting.md) | Shared content-addressed scene cache + disk accounting, cleanup, telemetry rotation and LLM-cache GC (A-027) (plan-phase-2) | Story | P1 | v1 | todo |
| [S-3.9.4](./stories/S-3.9.4-delete-project-forget-media.md) | Delete project / forget media — remove derived data, tombstone telemetry, never delete published snapshots (plan-phase-2) | Story | P1 | v1 | todo |
| [S-2.9.15](./stories/S-2.9.15-two-phase-prefilter-cheap-before-metadata.md) | Two-phase pre-filter — cheap quality/dedup pass before expensive rich-metadata extraction (plan-phase-3) | Story | P2 | v1 | todo |
| [S-3.1.5](./stories/S-3.1.5-hardware-probe.md) | Hardware probe — GPU / VRAM / RAM detected and persisted at setup (plan-phase-3) | Story | P2 | v1 | todo |
| [S-3.5.6](./stories/S-3.5.6-effort-level-plumbing.md) | Effort-level plumbing — make L1–L3 reach the job (or collapse the picker) (plan-phase-2) | Story | P2 | v1 | todo |
| [S-3.5.7](./stories/S-3.5.7-trip-cast-review-ui.md) | Trip-cast review UI — name / promote / demote + coverage repair (A-018) (plan-phase-3) | Story | P2 | v1 | todo |
| [S-3.8.3](./stories/S-3.8.3-wire-profile-emitters.md) | Wire the profile emitters — approve / refine / publish / cancel / effort-override events, derive at job end (plan-phase-2) | Story | P2 | v1 | todo |
| [S-2.9.4](./stories/S-2.9.4-crossfade-transitions-slow-tempo.md) | Crossfade transitions on slow-tempo music (ADR-0011/0012 design, unimplemented) (plan-phase-3) | Story | P3 | v1 | todo |

## Future phases (open, not yet scheduled)

Placeholder stories backfilled on 2026-06-14 plus later filings whose restart-plan phase is 4 or later. They open when their epic opens.

| Epic | Title | Phase | Epic status | Open children | IDs |
|---|---|---|---|---|---|
| [E-3.1](./epics/E-3.1-local-first-llm-runtime-operation-aware-router.md) | Local-first LLM runtime + operation-aware router | v1 | todo | 3 todo | S-3.1.1, S-3.1.2, S-3.1.3 |
| [E-3.2](./epics/E-3.2-live-job-continuous-ingest-multi-output-orchestration.md) | Live job — continuous ingest + multi-output orchestration | v1 | todo | 5 todo | S-3.2.1, S-3.2.2, S-3.2.3, S-3.2.4, S-3.2.5 |
| [E-3.3](./epics/E-3.3-multi-platform-connectors-instagram-facebook-x.md) | Multi-platform connectors — Instagram + Facebook + X | v1 | in-progress | 4 todo | S-3.3.3, S-3.3.4, S-3.3.6, S-3.3.7 |
| [E-3.4](./epics/E-3.4-reference-media-style-learning.md) | Reference-media style learning | v1 | todo | 2 todo | S-3.4.1, S-3.4.2 |
| [E-3.5](./epics/E-3.5-power-user-polish-bundle.md) | Power-user + polish bundle | v1 | todo | 4 todo | S-3.5.1, S-3.5.2, S-3.5.3, S-3.5.4 |
| [E-3.6](./epics/E-3.6-auto-photo-video-editing.md) | Auto photo / video editing | v1 | todo | 1 todo | S-3.6.1 |
| [E-3.7](./epics/E-3.7-music-sourcing-expansion.md) | Music sourcing expansion | v1 | todo | 2 todo | S-3.7.1, S-3.7.2 |
| [E-3.8](./epics/E-3.8-llm-driven-profile-re-derivation.md) | LLM-driven profile re-derivation | v1 | todo | 2 todo | S-3.8.1, S-3.8.2 |
| [E-3.9](./epics/E-3.9-cross-job-cache-full-reuse-class-semantics.md) | Cross-job cache — full reuse-class semantics | v1 | todo | 2 todo | S-3.9.1, S-3.9.2 |
| [E-4.1](./epics/E-4.1-full-mobile-ui.md) | Full mobile UI | v2 | todo | 1 todo | S-4.1.1 |
| [E-4.2](./epics/E-4.2-multi-agent-harness.md) | Multi-agent harness | v2 | todo | 1 todo | S-4.2.1 |
| [E-4.3](./epics/E-4.3-conversational-refinement-at-scale.md) | Conversational refinement at scale | v2 | todo | 2 todo | S-4.3.1, S-4.3.2 |
| [E-4.4](./epics/E-4.4-generated-music.md) | Generated music | v2 | todo | 1 todo | S-4.4.1 |
| [E-4.5](./epics/E-4.5-the-trip-package-autonomous-multi-artifact-creation-north-st.md) | The Trip Package — autonomous multi-artifact creation (north star) | v2 | todo | 5 todo | S-4.5.1, S-4.5.2, S-4.5.3, S-4.5.4, S-4.5.5 |
| [E-4.6](./epics/E-4.6-ai-crowd-removal.md) | AI crowd removal | v2 | todo | 1 todo | S-2.9.7 |
| [E-5.1](./epics/E-5.1-hosted-infrastructure.md) | Hosted infrastructure | v3 | todo | 1 todo | S-5.1.1 |
| [E-5.2](./epics/E-5.2-multi-tenancy-auth-billing.md) | Multi-tenancy + auth + billing | v3 | todo | 1 todo | S-5.2.1 |
| [E-5.3](./epics/E-5.3-public-launch.md) | Public launch | v3 | todo | 1 todo | S-5.3.1 |

## Recently Done (since 2026-06-11)

| ID | Title | Type | Done |
|---|---|---|---|
| [S-2.13.4](./stories/S-2.13.4-public-trust-docs-pass.md) | Public-trust docs pass — OVERVIEW, README, CLAUDE.md, ROADMAP, GROOMED, ARCHITECTURE, PIPELINE_DATAFLOW, headers, RAW_VISION addenda | Story | 2026-10-25 |
| [S-2.13.3](./stories/S-2.13.3-feedback-inbox-triage.md) | Feedback inbox triage — close the A-023 loop for the 11 rows still status=new | Story | 2026-10-25 |
| [S-2.13.2](./stories/S-2.13.2-d057-mvp-closure-and-honest-preflight.md) | D-057 MVP-closure decision + honest MVP.md pre-flight | Story | 2026-10-25 |
| [S-3.3.2](./stories/S-3.3.2-facebookconnector-xconnector.md) | FacebookConnector (Page video) | Story | 2026-10-24 |
| [S-3.3.1](./stories/S-3.3.1-instagramconnector-graph-api-facebook-login.md) | InstagramConnector — env-var credentials, dry-run only, never live-tested | Story | 2026-10-24 |
| [S-2.13.6](./stories/S-2.13.6-repo-and-session-hygiene.md) | Repo + session hygiene — worktree, .scratch, launch.json, hook allow entry, lock file, metadata, stale assets | Story | 2026-10-24 |
| [S-2.13.1](./stories/S-2.13.1-tracker-reconciliation-pr.md) | Tracker reconciliation PR — regenerate BOARD from frontmatter and fix every known contradiction | Story | 2026-10-24 |
| [S-2.11.1](./stories/S-2.11.1-snappier-fuller-edits.md) | Snappier, fuller edits — duration caps + min-video + coverage + per-viewpoint balance | Story | 2026-10-24 |
| [S-2.9.20](./stories/S-2.9.20-investigate-las-vegas-absent-from-curation.md) | Investigate why Las Vegas was absent from the curated video | Story | 2026-10-24 |
| [S-2.6.5](./stories/S-2.6.5-frontend-person-and-privacy.md) | Frontend — Person library page + privacy panel | Story | 2026-10-24 |
| [S-2.6.3](./stories/S-2.6.3-privacy-pipeline.md) | Privacy pipeline — EXIF strip + face-blur + cache | Story | 2026-10-24 |
| [S-2.6.1](./stories/S-2.6.1-person-library-backend.md) | Person library backend — CRUD API + reference-collage builder | Story | 2026-10-24 |
| [S-2.5.3](./stories/S-2.5.3-music-video-ui.md) | Frontend mode picker + section-to-media NL textarea | Story | 2026-10-24 |
| [S-2.5.2](./stories/S-2.5.2-music-video-stages.md) | Music-video mode through Stages 5/6/7 + section-to-media NL | Story | 2026-10-24 |
| [S-2.5.1](./stories/S-2.5.1-music-analyzer-and-cut-grid.md) | MusicAnalyzer (librosa-only) + CutGrid + MusicAnalysis Pydantic model | Story | 2026-10-24 |
| [E-2.10](./epics/E-2.10-feedback-driven-curation-quality.md) | Feedback-driven curation quality — coverage, balance, video, specialness | Epic | 2026-10-24 |
| [E-2.8](./epics/E-2.8-youtube-publish.md) | YouTube publish — OAuth + resumable upload + audit log | Epic | 2026-10-24 |
| [E-2.7](./epics/E-2.7-agentic-refinement-and-second-guess.md) | Agentic refinement (N-009) + orchestrator second-guess | Epic | 2026-10-24 |
| [E-2.6](./epics/E-2.6-person-library-and-privacy-panel.md) | Person library + face recognition (N-008) + privacy panel (with N-011 schema) | Epic | 2026-10-24 |
| [E-2.5](./epics/E-2.5-music-video-mode-and-section-to-media-nl.md) | Music-video mode + section-to-media NL mapping | Epic | 2026-10-24 |
| [S-2.12.4](./stories/S-2.12.4-title-card-refinement.md) | Title-card refinement + re-injection on refine | Story | 2026-07-01 |
| [S-2.12.3](./stories/S-2.12.3-agentic-refinement-loop.md) | Agentic refinement loop on the shared abstractions (flagship) | Story | 2026-07-01 |
| [S-2.12.2](./stories/S-2.12.2-positional-tempo-softalign-levers.md) | Positional/tempo/soft-align duration levers wired into initial planning | Story | 2026-07-01 |
| [S-2.12.1](./stories/S-2.12.1-plan-directive-shaping-model.md) | PlanDirective shaping model + Stage-6 directive consumption (no-op default) | Story | 2026-07-01 |
| [S-2.10.7](./stories/S-2.10.7-bump-llm-routing-current-models.md) | Bump LLM routing to current models (Opus 4.8 / Sonnet 4.6) + cache-token bump | Story | 2026-07-01 |
| [S-2.10.6](./stories/S-2.10.6-stage4-capture-day-stratified-budget.md) | Stage 4 capture-day stratified budget (replace global top-K) | Story | 2026-07-01 |
| [S-2.10.5](./stories/S-2.10.5-named-destination-coverage-guarantee.md) | Named-destination coverage guarantee (brief intent → reserve → instruct) | Story | 2026-07-01 |
| [E-2.12](./epics/E-2.12-open-ended-refinement-and-shared-curation-levers.md) | Open-ended refinement layer + shared curation levers | Epic | 2026-07-01 |
| [S-2.11.7](./stories/S-2.11.7-ai-title-text-from-brief.md) | AI-written splash-card title from the brief (heuristic fallback) | Story | 2026-06-30 |
| [S-2.11.6](./stories/S-2.11.6-music-mood-section-matching.md) | Music mood/tempo/section analysis → match media to sections | Story | 2026-06-30 |
| [S-2.11.5](./stories/S-2.11.5-ai-title-splash-card.md) | Opt-in AI title/splash card (remote image-gen) | Story | 2026-06-30 |
| [S-2.11.4](./stories/S-2.11.4-burst-montage-clip-type.md) | Burst-montage clip type for dense same-backdrop clusters | Story | 2026-06-30 |
| [S-2.11.3](./stories/S-2.11.3-richer-live-module-progress-viz.md) | Richer live module/decision progress visualization | Story | 2026-06-30 |
| [S-2.11.2](./stories/S-2.11.2-job-and-phase-level-feedback.md) | Feedback at the job and phase level (not only per-media) | Story | 2026-06-30 |
| [S-2.10.3](./stories/S-2.10.3-stage5-video-variety-balance-chronology.md) | Stage 5 judge — video share, variety, balance, strict-forward opener | Story | 2026-06-30 |
| [S-2.10.2](./stories/S-2.10.2-specialness-aware-stage4-selection.md) | Specialness-aware Stage 4 selection (4-term score + rescue + tie-breaks) | Story | 2026-06-30 |
| [S-2.10.1](./stories/S-2.10.1-feedback-hang-and-inspect-diagnostics.md) | Fix feedback-modal hang + complete inspect diagnostics (F8) | Story | 2026-06-30 |
| [E-2.11](./epics/E-2.11-snappier-edits-output-polish-observability.md) | Snappier, fuller edits + output polish + observability (round-2 feedback) | Epic | 2026-06-30 |
| [S-2.9.16](./stories/S-2.9.16-snapshot-keyed-inspect-feedback-view.md) | Snapshot-keyed "Inspect & give feedback" view — review completed jobs after a restart (no re-run) | Story | 2026-06-18 |
| [S-2.9.14](./stories/S-2.9.14-cost-metering-accuracy-and-failure-surfacing.md) | Token-accurate cost metering + credit-exhausted error surfacing + accurate Stage-2 progress | Story | 2026-06-17 |
| [S-2.9.13](./stories/S-2.9.13-one-click-spirit-realignment.md) | Re-align product positioning to the 1-click media-to-video creator spirit (docs + app UI) | Story | 2026-06-14 |
| [S-2.9.12](./stories/S-2.9.12-auto-trip-cast-face-inventory-groupcrowd-coverage-a-018-anal.md) | Auto trip cast — face inventory + group/crowd + coverage (A-018, analysis half) | Story | 2026-06-14 |
| [S-2.9.11](./stories/S-2.9.11-rich-metadata-enrichment-shot-type-expression-safety-special.md) | Rich-metadata enrichment — shot type, expression, safety, specialness (A-022) | Story | 2026-06-14 |
| [S-2.9.10](./stories/S-2.9.10-media-chronology-capture-time-gps-extraction-a-021.md) | Media chronology — capture-time + GPS extraction (A-021) | Story | 2026-06-14 |
| [S-2.9.9](./stories/S-2.9.9-developer-tracker-pages.md) | Developer tracker pages — feedback/enhancement tracker + workplan tracker | Story | 2026-06-14 |
| [S-2.9.8](./stories/S-2.9.8-in-app-feedback-loop.md) | In-app feedback loop — per-phase diagnostics + decision-level feedback | Story | 2026-06-14 |
| [S-2.9.6](./stories/S-2.9.6-semantic-near-duplicate-suppression.md) | Semantic near-duplicate suppression — best-of-burst selection in Stage 4 | Story | 2026-06-11 |
| [S-2.9.5](./stories/S-2.9.5-cheap-first-analysis-hardening.md) | Cheap-first analysis hardening — thumbnails to LLMs + time-bounded scene sampling | Story | 2026-06-11 |
| [S-2.9.3](./stories/S-2.9.3-persist-project-brief-and-name.md) | Persist brief + name on project rows at job submit | Story | 2026-06-11 |
| [S-2.9.2](./stories/S-2.9.2-dashboard-project-list-render-history.md) | Dashboard project list + render history (replace M0 stub) | Story | 2026-06-11 |
| [S-2.9.1](./stories/S-2.9.1-validation-hotfixes-2026-06-11.md) | Validation hot-fixes 2026-06-11 — cache poisoning, beat-snap, audio fade, EXIF | Story | 2026-06-11 |

## Previously Done

| Epic | Title | Stories | Done |
|---|---|---|---|
| [E-2.4](./epics/E-2.4-ui-mvp-loop-closed.md) | UI MVP loop closed — drag-drop, brief, effort-level, progress, preview | S-2.4.1..5 (5 stories) | 2026-05-05 |
| [E-2.3](./epics/E-2.3-render-and-standard-mode.md) | Render + standard mode — Stage 6 plan compile + Stage 7 ffmpeg render | S-2.3.1..4 (4 stories) | 2026-05-04 |
| [E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md) | Headless curation through Stage 5 — LLM stack + pipeline through ArcJudgment | S-2.2.1..8 (8 stories) | 2026-05-04 |
| [E-2.1](./epics/E-2.1-scaffolding.md) | Scaffolding — pip install + CLI + FastAPI + React shell + first-time-setup | S-2.1.1..6 (6 stories) | 2026-05-03 |
| [E-1.4](./epics/E-1.4-roadmap-and-mvp-scoping.md) | Roadmap and MVP scoping | S-1.4.1..2 (2 stories) | 2026-05-03 |
| [E-1.3](./epics/E-1.3-architecture-grooming.md) | Architecture grooming | S-1.3.1..3 (3 stories) | 2026-04-28 |
| [E-1.5](./epics/E-1.5-auto-merge-policy.md) | Auto-merge policy for skill and feature PRs | S-1.5.1..1 (1 stories) | 2026-04-26 |
| [E-1.2](./epics/E-1.2-vision-grooming.md) | Vision grooming | S-1.2.1..1 (1 stories) | 2026-04-26 |
| [E-1.1](./epics/E-1.1-repo-scaffolding.md) | Repo scaffolding | S-1.1.1..1 (1 stories) | 2026-04-25 |

## Canceled

| ID | Title | Type | Canceled |
|---|---|---|---|
| [S-2.6.4](./stories/S-2.6.4-n011-privacy-routing.md) | N-011 privacy-routing schema in LLMRouter | Story | 2026-10-24 |

## Initiative index

| ID | Title | Status | Phase | Epics |
|---|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | done | scaffolding | 5 epics: 5 done |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | in-progress | mvp | 13 epics: 11 done, 2 in-progress |
| [I-3](./initiatives/I-3-v1-local-first-live-job-multi-platform-style-polish.md) | v1 — Local-first + live job + multi-platform + style + polish | in-progress | v1 | 11 epics: 1 in-progress, 10 todo |
| [I-4](./initiatives/I-4-v2-mobile-multi-agent-conversational-generated-music-trip-pa.md) | v2 — Mobile + multi-agent + conversational + generated music + Trip Package | backlog | v2 | 6 epics: 6 todo |
| [I-5](./initiatives/I-5-v3-hosted-multi-tenant-saas.md) | v3 — Hosted multi-tenant SaaS | backlog | v3 | 3 epics: 3 todo |

## Status tally (from frontmatter)

Regenerate with `python scripts/tracker_board.py`; `--check` fails when this file drifts from the item files.

| Type | backlog | canceled | deferred | done | in-progress | todo | Total |
|---|---|---|---|---|---|---|---|
| Initiative | 2 | 0 | 0 | 1 | 2 | 0 | 5 |
| Epic | 0 | 0 | 0 | 16 | 3 | 19 | 38 |
| Story | 0 | 1 | 1 | 75 | 1 | 67 | 145 |
| Task | 0 | 0 | 0 | 30 | 0 | 0 | 30 |
| **All** | 2 | 1 | 1 | 122 | 6 | 86 | 218 |
