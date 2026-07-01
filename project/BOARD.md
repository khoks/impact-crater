# Board

> **Last updated:** 2026-07-01 — **Open-ended refinement + shared curation levers shipped (E-2.12, D-056).** From "pick up S-2.10.4/5/6/7/8 + S-2.11.5/6 and make refinement handle arbitrary NL requests": built two shared levers — **PlanDirective** (ADR-0019: duration/positional/tempo shaping Stage 6 consumes + refinement emits) and **ReservationSet** (S-2.10.5: source-agnostic must-keep through Stage 4 = the **Vegas fix**) — then the **agentic refinement loop** (S-2.12.3) whose tools are thin wrappers over them (pacing → re-run Stage 6 only; coverage → re-Stage-4 + re-judge; content → re-judge; renders a child snapshot). Plus **S-2.10.4** cast merge-pass, **S-2.10.6** capture-day stratified budget (A/B-gated), **S-2.10.7** model bump (Opus 4.8 / Sonnet 4.6, incl. the Opus-4.8-drops-`temperature` fix), **S-2.10.8** pluggable local-embedder interface (stub; weights deferred), **S-2.11.5b** title-card cost line-item. Backend **464 pass**; frontend typecheck + 38 vitest green. **Verified live**: both a pacing refinement ("beginning clips 50% longer, shrink the photos around them") and a coverage refinement ("don't drop the Zion shots, lean on landscapes") were interpreted → the right lever → re-rendered a child snapshot end-to-end. ADR-0019/0020; **knowledge swept:** D-056. **Op note:** restart the detached dev server after backend commits before UI-testing.
> **Earlier (2026-06-30):** **AI-written splash-card title shipped (S-2.11.7, [PR #69](https://github.com/khoks/impact-crater/pull/69), D-055).** P3 polish follow-up to S-2.11.5: when the user doesn't type a `title_text`, the opt-in title card's auto-derived title now comes from a cheap Tier-S `generate_title_text` op (brief + modal year → clean 2–5 word title, place-name typo-fixing) that **reuses the structured-text primitive** (`parse_user_brief` + `{title}` schema) rather than widening the `LLMClient` protocol; the old first-clause heuristic is kept as the fail-soft fallback, and an explicit `title_text` short-circuits the call. **Knowledge swept:** D-055, A-026.
> **Earlier (2026-06-30):** **Round-2 output-feedback pass shipped (E-2.11, [PR #67](https://github.com/khoks/impact-crater/pull/67), D-054).** From the user's 10-point round-2 feedback on the SW-US re-renders, delivered all of E-2.11 on the "do all" instruction: **S-2.11.1** snappier/fuller edits (per-clip duration band photos 1–3s / video ≥2s, coverage of every location+time) + **T-2.11.1.6** candidate-level ≤4/viewpoint cap; **S-2.11.2** job- and phase-level feedback; **S-2.11.3** richer live progress (per-stage sub-module chips); **S-2.11.4** burst-montage clip type (dense same-backdrop bursts → one ~0.5s-per-member sequence); **S-2.11.5** opt-in AI title/splash card (remote image-gen + cast faces + title/year, fail-soft); **S-2.11.6** music mood/section matching (both modes). Backend suite **419 pass**; verified via reconstruction render (title card + 44-clip/115s snappy arc) and **live through the app UI** (toggle, three feedback levels, sub-module progress chips, a full job submitted → rendered opening on the AI title card). Also marked **S-2.10.1/2/3 done** (shipped + output-verified). **Op note:** a long-running detached dev server serves stale Python modules — restart it after backend commits before UI-testing new server-side behaviour. **Knowledge swept:** D-054.
> **Earlier (2026-06-29):** **Feedback-driven curation-quality pass (E-2.10).** Inspected the D-014 SW-US-trip job (snapshot b4b73c7b1fe044b7) against its media, submitted 8 per-decision feedback items via the in-app loop, and from them shipped: **S-2.10.1** (fix the feedback-modal hang + video scene thumbnails + drop-card scores), **S-2.10.2** (specialness-aware Stage 4: 4-term score + quality-floor rescue + tie-breaks), **S-2.10.3** (Stage 5 video-share/variety/balance + chronological opener + MOTION/STILL candidate tags) — all tested (401 backend pass, frontend typechecks) on a feature branch pending the user's live-output verification. Partial: **S-2.10.4** (cast conjunctive group gate landed; merge-pass/detection pending). Filed for next: **S-2.10.5** (named-destination coverage — the real Vegas fix, P0), **S-2.10.6** (capture-day stratified budget), **S-2.10.7** (model bump Opus 4.8/Sonnet 4.6), **S-2.10.8** (local CLIP/SigLIP embedder). Resolved **S-2.9.20** (Vegas root cause = no brief-aware coverage → S-2.10.5). **Knowledge swept:** ADR-0017, ADR-0018, D-053.
> **Earlier (2026-06-18):** **MVP D-014 validation PASSED + cost/UX hardening.** The user ran a real **1,663-asset SW-US-trip job** (1,481 photos + 182 videos → 2,067 shots) end-to-end → a publish-ready **108s Story Video at confidence 0.85**, evaluated good against the brief — **the D-014 MVP gate is met**. This session also shipped **S-2.9.13** (1-click positioning realign across 9 docs + the app UI + RAW_VISION addenda, D-050), **S-2.9.14** (token-accurate cost metering after a ~5× undercount + credit-exhausted error surfacing + accurate Stage-2 progress; daily cap $50→$100; D-048), and **S-2.9.16** (snapshot-keyed Inspect & Feedback so finished jobs stay reviewable after a restart). Filed: **S-2.9.15** (two-phase pre-filter, D-049), **S-2.9.17** (faststart render), **S-2.9.18** (token-aware pre-job estimate), **S-2.9.19** (persist job registry, A-025), **S-2.9.20** (Las Vegas absent from curation). GitHub Pages docs site + branding live (D-052). **Knowledge swept:** D-048..D-052 + A-025 logged.
> **How to read this:** Hand-maintained mirror of frontmatter `status:` values. The `work-tracker` skill refreshes this file at end-of-session. If you see drift, re-derive from `grep -l "status:" project/{initiatives,epics,stories,tasks}/*.md`.

---

## In Progress

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | Initiative | P0 | mvp |
| [E-2.9](./epics/E-2.9-cross-project-profile-mvp.md) | Cross-project profile + polish + **D-014 validation** (reopened 2026-06-11) | Epic | P0 | mvp |
| [S-2.10.8](./stories/S-2.10.8-local-image-embedder.md) | Local CLIP/SigLIP embedder — pluggable interface + stub landed; real weights backend deferred (GPU) | Story | P1 | v1 |

## Up Next (Ready)

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [S-2.10.5](./stories/S-2.10.5-named-destination-coverage-guarantee.md) | **Named-destination coverage guarantee (the real Las-Vegas fix; brief-parse + reserve + instruct judge)** | Story | P0 | mvp |
| [S-2.9.18](./stories/S-2.9.18-token-aware-pre-job-cost-estimate.md) | Token-aware pre-job cost estimate (align preview with the accurate meter; D-048) | Story | P2 | mvp-hardening |
| [S-2.10.7](./stories/S-2.10.7-bump-llm-routing-current-models.md) | Bump LLM routing to current models (Opus 4.8 / Sonnet 4.6) + cache-token bump | Story | P2 | mvp |
| [S-2.9.17](./stories/S-2.9.17-faststart-render-instant-preview.md) | Faststart render so inline previews load instantly | Story | P3 | mvp-hardening |

## Backlog (queued)

| ID | Title | Type | Priority | Phase |
|---|---|---|---|---|
| [S-2.9.7](./stories/S-2.9.7-ai-crowd-removal.md) | AI crowd removal — inpaint non-group people (remote default / local optional, D-044) | Story | P3 | v2 |
| [S-2.9.4](./stories/S-2.9.4-crossfade-transitions-slow-tempo.md) | Crossfade transitions on slow-tempo music (ADR-0011/0012) | Story | P3 | v1 |
| [S-2.9.15](./stories/S-2.9.15-two-phase-prefilter-cheap-before-metadata.md) | Two-phase pre-filter — cheap pass before rich metadata (~½ Tier-M cost saved; D-049) | Story | P2 | v1 |
| [S-2.9.19](./stories/S-2.9.19-persist-job-registry-survive-restart.md) | Persist job registry so live/preview survive a restart (A-025) | Story | P2 | v1 |
| [S-2.10.8](./stories/S-2.10.8-local-image-embedder.md) | Local CLIP/SigLIP image embedder replacing caption-then-embed (ADR-0018; F2/F3 root cause) | Story | P1 | v1 |
| [S-2.10.6](./stories/S-2.10.6-stage4-capture-day-stratified-budget.md) | Stage 4 capture-day stratified budget replacing global top-K (A/B-gated) | Story | P2 | v1 |

> **2026-06-11 prep-phase overhaul (D-043):** the preparation phase was rebuilt before the heavier features. **Delivered:** A-021 media chronology (EXIF/filename/mtime reconciliation + GPS read; the judge now orders forward-in-time), A-022 rich-metadata enrichment (shot type, per-person expression, safety, specialness, obstructions), A-016 cheap-first analysis (~47× smaller payloads), A-017 best-of-burst semantic dedup.
> **2026-06-11 auto trip cast (D-044):** A-018 analysis half delivered — detect→embed→cluster→group/crowd-by-recurrence-breadth→coverage report, pluggable backends (gemini cloud default / insightface optional local); also fixed face detection (mediapipe 0.10.35 dropped `mp.solutions`, which had silently disabled privacy-blur too). **Next:** A-019 crowd removal (remote-API default / local-generative optional per D-044) builds on the cast. Trip Package (A-020/N-013, v2) stays gated on single-video quality (D-042).

## Recently Done

| ID | Title | Type | Done |
|---|---|---|---|
<<<<<<< HEAD
| **[E-2.12](./epics/E-2.12-open-ended-refinement-and-shared-curation-levers.md)** | **Open-ended refinement + shared curation levers — PlanDirective + ReservationSet + agentic refinement loop; renders a child snapshot [D-055, ADR-0019/0020]** | Epic | 2026-07-01 |
| **[S-2.12.3](./stories/S-2.12.3-agentic-refinement-loop.md)** | **Agentic refinement loop — interprets arbitrary NL → pacing/coverage/content levers → child snapshot (live-verified)** | Story | 2026-07-01 |
| **[S-2.10.5](./stories/S-2.10.5-named-destination-coverage-guarantee.md)** | **Named-destination coverage — the Vegas fix + shared ReservationSet (brief-parse → reserve through Stage 4 → instruct judge)** | Story | 2026-07-01 |
| **[S-2.12.1](./stories/S-2.12.1-plan-directive-shaping-model.md)–[S-2.12.2](./stories/S-2.12.2-positional-tempo-softalign-levers.md)** | **PlanDirective shaping model + positional/tempo/soft-align levers wired into planning [ADR-0019]** | Stories | 2026-07-01 |
| **[E-2.10](./epics/E-2.10-feedback-driven-curation-quality.md)** | **Feedback-driven curation quality — S-2.10.1–8 all landed (specialness Stage 4, video/variety judge, cast merge, stratified budget, model bump, embedder interface)** | Epic | 2026-07-01 |
=======
| **[S-2.11.7](./stories/S-2.11.7-ai-title-text-from-brief.md)** | **AI-written splash-card title from the brief — cheap Tier-S `generate_title_text` op (clean 2–5 words, typo-fixing) + heuristic fallback; P3 polish on S-2.11.5** | Story | 2026-06-30 |
>>>>>>> origin/master
| **[E-2.11](./epics/E-2.11-snappier-edits-output-polish-observability.md)** | **Round-2 output feedback — snappier edits + montage + AI title card + richer feedback/observability (6 stories + T-2.11.1.6) [PR #67, D-054]** | Epic | 2026-06-30 |
| **[S-2.11.5](./stories/S-2.11.5-ai-title-splash-card.md)** | **Opt-in AI title/splash card — remote image-gen bg + cast faces + title/year, fail-soft; verified live in-app [#7]** | Story | 2026-06-30 |
| **[S-2.11.4](./stories/S-2.11.4-burst-montage-clip-type.md)** | **Burst-montage clip type — dense same-backdrop bursts → one ~0.5s-per-member sequence (Stage 4 detect → 6 collapse → 7 render) [#5]** | Story | 2026-06-30 |
| **[S-2.11.3](./stories/S-2.11.3-richer-live-module-progress-viz.md)** | **Richer live progress — per-stage sub-module chips in the job view [#10]** | Story | 2026-06-30 |
| **[S-2.11.2](./stories/S-2.11.2-job-and-phase-level-feedback.md)** | **Job- and phase-level feedback in the inspect UI (not only per-media) [#9]** | Story | 2026-06-30 |
| **[S-2.11.1](./stories/S-2.11.1-snappier-fuller-edits.md)** | **Snappier, fuller edits — per-clip duration band + min-video + coverage + T-2.11.1.6 ≤4/viewpoint cap [#1-4,6]** | Story | 2026-06-30 |
| **[S-2.11.6](./stories/S-2.11.6-music-mood-section-matching.md)** | **Music mood/tempo/section matching surfaced to the judge in both modes [#8]** | Story | 2026-06-30 |
| **[S-2.10.1](./stories/S-2.10.1-feedback-hang-and-inspect-diagnostics.md)–[S-2.10.3](./stories/S-2.10.3-stage5-video-variety-balance-chronology.md)** | **E-2.10 curation-quality: feedback-hang fix + inspect diagnostics, specialness-aware Stage 4, Stage 5 video/variety/balance — shipped + output-verified** | Stories | 2026-06-30 |
| **[S-2.9.20](./stories/S-2.9.20-investigate-las-vegas-absent-from-curation.md)** | **Vegas-absent investigated — root cause = all 37 NV shots dropped pre-judge (no brief-aware coverage); fix tracked as S-2.10.5** | Story | 2026-06-29 |
| **8 feedback items** | **Inspected snapshot b4b73c7b1fe044b7 vs its media; submitted 8 per-decision feedback items via the in-app loop (ids 5–12)** | Milestone | 2026-06-29 |
| **D-014 validation** | **MVP gate PASSED — real 1,663-asset SW-US-trip job → publish-ready 108s Story Video (conf 0.85), good vs brief** | Milestone | 2026-06-18 |
| **[S-2.9.16](./stories/S-2.9.16-snapshot-keyed-inspect-feedback-view.md)** | **Snapshot-keyed Inspect & Feedback — review finished jobs after a restart [A-025]** | Story | 2026-06-18 |
| **[S-2.9.14](./stories/S-2.9.14-cost-metering-accuracy-and-failure-surfacing.md)** | **Token-accurate cost metering + credit-exhausted surfacing + accurate Stage-2 progress; cap → $100 [D-048]** | Story | 2026-06-18 |
| **[S-2.9.13](./stories/S-2.9.13-one-click-spirit-realignment.md)** | **1-click positioning realign — 9 docs + app UI + RAW_VISION addenda [D-050]** | Story | 2026-06-18 |
| **[S-2.9.9](./stories/S-2.9.9-developer-tracker-pages.md)** | **Developer tracker pages — feedback tracker + workplan tracker (editable priority) [A-024/D-047]** | Story | 2026-06-14 |
| **[S-2.9.8](./stories/S-2.9.8-in-app-feedback-loop.md)** | **In-app feedback loop — per-phase diagnostics + decision-level feedback; +live-during-execution + page screenshots [A-023/N-015/D-045/D-046]** | Story | 2026-06-14 |
| **A-018 / N-012** | **Auto trip cast — face inventory + group/crowd + coverage (analysis half) [D-044]** | Feature | 2026-06-11 |
| **[S-2.9.5](./stories/S-2.9.5-cheap-first-analysis-hardening.md)** | **Cheap-first analysis (1024px renditions + scene subdivision) [D-043]** | Story | 2026-06-11 |
| **[S-2.9.6](./stories/S-2.9.6-semantic-near-duplicate-suppression.md)** | **Best-of-burst semantic dedup (time-windowed) [D-043]** | Story | 2026-06-11 |
| **A-021 / A-022** | **Media chronology + GPS + rich-metadata enrichment (prep-phase overhaul, D-043)** | Feature | 2026-06-11 |
| **[S-2.9.2](./stories/S-2.9.2-dashboard-project-list-render-history.md)** | **Dashboard project list + render history + inline playback (+ Content-Disposition fix)** | Story | 2026-06-11 |
| **[S-2.9.3](./stories/S-2.9.3-persist-project-brief-and-name.md)** | **Persist brief + name on project rows at job submit** | Story | 2026-06-11 |
| **[S-2.9.1](./stories/S-2.9.1-validation-hotfixes-2026-06-11.md)** | **Validation hot-fixes 2026-06-11 — cache poisoning (D-040), beat-snap (D-041), audio fade, EXIF; PRs #35–#37** | Story | 2026-06-11 |

## Previously Done (last sessions)

| ID | Title | Type | Done |
|---|---|---|---|
| **[E-2.6](./epics/E-2.6-person-library-and-privacy-panel.md)** | **Person library + privacy panel (M5) — N-008 collage builder + EXIF strip + face blur + UI; 2 stories deferred-to-v1** | Epic | 2026-05-05 |
| [S-2.6.1, S-2.6.3, S-2.6.5](./stories/) | M5 stories shipped | Stories | 2026-05-05 |
| **[E-2.5](./epics/E-2.5-music-video-mode-and-section-to-media-nl.md)** | **Music-video mode + section-to-media NL (M4) — librosa MusicAnalyzer + cut grid + Stage 5/6 wiring + UI** | Epic | 2026-05-05 |
| [S-2.5.1..3](./stories/) | M4 stories (analyzer + cut-grid + pipeline wiring + frontend) | Stories | 2026-05-05 |
| **[E-2.4](./epics/E-2.4-ui-mvp-loop-closed.md)** | **UI MVP loop closed (M3) — React UI + async jobs + WS + preview** | Epic | 2026-05-05 |
| [S-2.4.1](./stories/S-2.4.1-async-jobs-ws-folder-scan.md) | Async jobs + WS + folder scan + cost preview | Story | 2026-05-05 |
| [S-2.4.2](./stories/S-2.4.2-dashboard-and-new-project.md) | Dashboard + New Project flow | Story | 2026-05-05 |
| [S-2.4.3](./stories/S-2.4.3-effort-level-and-cost-preview.md) | Effort-level UX + cost preview + submit | Story | 2026-05-05 |
| [S-2.4.4](./stories/S-2.4.4-progress-and-preview.md) | In-job progress + live spend + preview UI | Story | 2026-05-05 |
| [S-2.4.5](./stories/S-2.4.5-settings-panel.md) | Settings panel | Story | 2026-05-05 |
| **[E-2.3](./epics/E-2.3-render-and-standard-mode.md)** | **Render + standard mode (M2) — Stages 6-7 + render API** | Epic | 2026-05-04 |
| [S-2.3.1..4](./stories/) | M2 stories (ffmpeg resolver + Stage 6 + Stage 7 + render API) | Stories | 2026-05-04 |
| **[E-2.2](./epics/E-2.2-headless-curation-through-stage-5.md)** | **Headless curation through Stage 5 (M1) — full LLM stack + Stages 1-5 + headless API** | Epic | 2026-05-04 |
| [S-2.2.1..8](./stories/) | M1 stories (LLMClient + router + telemetry + quota + worker pool + Stages 1-5 + headless endpoint) | Stories | 2026-05-04 |
| [E-2.1](./epics/E-2.1-scaffolding.md) | Scaffolding (M0) — first commit of code | Epic | 2026-05-03 |

---

## Initiative index

| ID | Title | Status | Phase |
|---|---|---|---|
| [I-1](./initiatives/I-1-project-foundation.md) | Project foundation | **done** (2026-05-03) | scaffolding |
| [I-2](./initiatives/I-2-mvp.md) | MVP — Story Video to YouTube | **in-progress** (E-2.9 reopened 2026-06-11 for D-014 validation; M0..M8 code done) | mvp |
| [I-3](./initiatives/I-3-v1-local-first-live-job-multi-platform-style-polish.md) | v1 — Local-first + live job + multi-platform + style + polish | **backlog** (epics E-3.1..E-3.9 backfilled 2026-06-14) | v1 |
| [I-4](./initiatives/I-4-v2-mobile-multi-agent-conversational-generated-music-trip-pa.md) | v2 — Mobile + multi-agent + conversational + generated music + Trip Package | **backlog** (epics E-4.1..E-4.5 backfilled 2026-06-14; **E-4.5 = the Trip Package north star, A-020/N-013, gated by D-042**) | v2 |
| [I-5](./initiatives/I-5-v3-hosted-multi-tenant-saas.md) | v3 — Hosted multi-tenant SaaS | **backlog** (epics E-5.1..E-5.3 backfilled 2026-06-14) | v3 |

> **2026-06-14 roadmap backfill (A-024 follow-up):** the full v1/v2/v3 plan from `docs/roadmap/ROADMAP.md` + `GROOMED_FEATURES.md` was materialized into `project/` (I-3/I-4/I-5 + 17 epics + ~34 stories) so the in-app **workplan tracker** shows the whole plan, not just current+next phase. Also backfilled stories for delivered-but-unstoried features: **S-2.9.10** (A-021 chronology), **S-2.9.11** (A-022 metadata), **S-2.9.12** (A-018 auto trip cast). Future-phase items are `todo`/`backlog`; statuses are coarse and get refined when each phase opens.
