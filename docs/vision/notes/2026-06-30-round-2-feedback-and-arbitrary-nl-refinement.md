# 2026-06-30 — Round-2 output feedback and "make refinement handle arbitrary NL requests" (reconstruction)

> **Reconstructed from the tracker and decision records — only the phrases in quotation marks are the user's recorded words.** The Claude Code session transcripts of 2026-06-30 (and of the 2026-07-01 continuation) were not retained, so there is no verbatim text for either instruction. This file was written on 2026-10-25 (restart plan Phase 0, S-2.13.4) from the records those sessions produced the same day: tracker epics and stories, decision-log entries, PR titles and the board summary. Every quoted fragment is copied exactly from the cited record. Those records are same-day summaries written by Claude, so a quoted fragment is the *recorded* wording, which may itself paraphrase what the user typed. Everything outside quotation marks is the 2026-10-25 author's reading of the records. If a transcript surfaces, add the verbatim text in a dated section at the end and leave this reconstruction in place.

## Why this file exists

`RAW_VISION.md`'s addenda stopped at 2026-06-14. The restart audit (`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md`) found that the two intent-level instructions of 2026-06-30 — the round-2 output feedback that became E-2.11 and the "arbitrary NL" refinement instruction that became E-2.12 — existed only inside tracker files, and that `docs/vision/notes/` had never been created. Two short addenda dated 2026-06-30 now sit in `RAW_VISION.md`, labelled as reconstructions, and point here for the fuller account.

## What happened, in order (from git and the tracker)

| When | Record | What |
|---|---|---|
| 2026-06-29 | PRs #65, #66 (d4ec922, bba2e13) | Knowledge-curator and work-tracker sweeps of the previous session (the E-2.10 feedback-driven curation fixes, D-053). |
| 2026-06-30 | E-2.11 created; D-054 | The user reviewed two re-renders of the SW-US trip and gave ten notes. Grouped A–D; Group A (S-2.11.1) built first. |
| 2026-06-30 | "do all" (E-2.11 activity log) | The remaining groups were built in the same session: S-2.11.2–S-2.11.6 + T-2.11.1.6. |
| 2026-06-30 | PR #67 adcf38d | `feat(curation): round-2 output feedback — snappier edits + montage + AI title card + richer feedback/observability [E-2.11]`. |
| 2026-06-30 | PR #68 4a04ed2 | Board/story statuses, OVERVIEW + PIPELINE_DATAFLOW refresh; E-2.11 done. |
| 2026-06-30 | PR #69 2bf1f3a; D-055; A-026 | S-2.11.7 AI-written splash-card title (the heuristic had produced "Early-April Through Zion Bryce Horseshow"). |
| 2026-06-30 | PRs #70, #71 (c8a10cc, 4cc0e13) | Knowledge-curator and work-tracker sweeps of session 321211ae. |
| 2026-06-30 | E-2.12 created; `docs/design/refinement_design.json` | The user's "pick up S-2.10.4/5/6/7/8 + S-2.11.5/6 and make refinement handle arbitrary NL requests" instruction; a six-agent design pass + synthesis produced the shared-lever plan and a nine-step build order. ADR-0019 is dated 2026-06-30. |
| 2026-07-01 | PR #72 2bf66b1; D-056; ADR-0020 | `feat: open-ended agentic refinement + shared curation levers (E-2.12) + S-2.10.4/5/6/7/8`. A live pacing and a live coverage refinement each re-rendered a child snapshot. |
| 2026-07-01 | PR #73 288c46f | S-2.12.4 title-card refinement + re-inject on refine; verified live with "rename to 'Desert Wandering', move to top, gold, bigger, drop year". |
| 2026-07-01 | PR #74 da34766 | Title-card glyph-folding fix. The last build commit before the pause that ended 2026-10-24. |

## Part 1 — The round-2 output feedback (→ E-2.11)

### Context

The first feedback round (2026-06-29, D-053 / E-2.10) had addressed coverage and balance defects in the real 1,663-asset south-west US trip job (snapshot `b4b73c7b1fe044b7`; its brief, as D-055 records it, was "A highlight video of our early-April trip through zion, bryce, horseshow bend, grand canyon, and las vegas"). The user then watched two re-renders and gave ten specific notes.

### The ten points, as recorded

D-054's Context (`docs/decisions/DECISIONS_LOG.md`, D-054) records them in two groups. Five observations about the edit — the "edits are too slow and too thin":

1. "5–8s held photos incl. an 8000ms opener"
2. "a jerky ~1s video clip"
3. "whole sub-locations/times within a park skipped"
4. "one viewpoint — Horseshoe Bend — given 4 slots"
5. "a 1–2 min video too short for a long trip"

and five asks, which D-054 counts as "four feature asks" because it folds the last two together:

6. "an opt-in AI title/splash card"
7. "an occasional 0.5s burst-montage for dense same-backdrop clusters"
8. "music mood/tempo/section-aware matching"
9. "job-/phase-level feedback"
10. "a much richer live module/decision progress view at the depth of the pipeline infographic"

The E-2.11 epic numbers the user's points #1–#10 and maps them to stories (Scope section): S-2.11.1 covers "#1,2,3,4,6"; S-2.11.4 burst-montage is "#5"; S-2.11.5 title card is "#7"; S-2.11.6 music is "#8"; S-2.11.2 job/phase feedback is "#9"; S-2.11.3 live view is "#10". So in the user's own numbering the five edit observations were #1–#4 and #6 and the burst-montage ask was #5; which observation carried which number is not recorded. The epic's Goal restates the whole: the edits are "too slow and too thin"; the target is "snappy, fully-covering" edits ("2–3s clips, every sub-location/time represented, no single viewpoint hogging the cut, no jerky <2s video flashes, no 5–8s held photos"), plus the output-polish asks, plus "much deeper observability + feedback" "at the depth of the NotebookLM pipeline infographic". The S-2.11.1 verification measured Horseshoe Bend at 6 clips in the judge's selection before the cap (vs. the "4 slots" the user saw in the rendered video); the two numbers describe different stages and are not a contradiction.

### Recorded user choices in the same review

- **Splash-card image generation = remote image-gen API, "chosen by the user"** (D-054 Decision); the alternative, "Local image-gen for the splash card (rejected by user — heavy GPU dependency; remote API chosen)" (D-054 Alternatives).
- **"do all"** — E-2.11's activity log: "All six stories (+ T-2.11.1.6) delivered on user's "do all" instruction"; `project/BOARD.md`'s 2026-06-30 summary records the same.
- Design choices made *for* the user and recorded as decisions, not as user words (D-054 Alternatives): respect the chosen duration and pack it densely rather than auto-extend the target for big trips; cap per-clip duration rather than select fewer clips; a 1 s safety floor instead of a hard 1.5 s per-clip minimum.

### The intent behind the feedback (author's reading)

A long group trip deserves a video that moves — a snappy, complete tour of everywhere the group went, not a slow slideshow of a few iconic spots — and the user wants to steer that at every grain: a single decision (the 2026-06-14 feedback loop), a whole phase, or the whole video. The live job view is part of the product, not a progress bar: it should show the modules and decisions executing at the depth of the pipeline infographic, continuing the 2026-06-14 "showing the prowess of the app" addendum. Music should shape the cut in every mode, not only in music-video mode (the records scope #8 as matching media to song sections "beyond music-video mode").

## Part 2 — "Make refinement handle arbitrary NL requests" (→ E-2.12)

### The instruction, as recorded

E-2.12's activity log says the epic was created "from the user's "pick up S-2.10.4/5/6/7/8 + S-2.11.5/6 and make refinement handle arbitrary NL requests" instruction". The epic's Goal records the examples the user "must be able to say":

- "insert more photos of Las Vegas"
- "don't drop Las Vegas even if its quality/impact is low"
- "make the clips in the beginning 50% longer / 2s longer and reduce the photos around them by 0.5s"
- "increase photo duration/frequency with the song's rising tempo in the later half, decrease with the falling tempo"

followed, in the epic's own words, by "and more we can't predict". The Goal then states how it should work: the prompt engineering must let the agent think from the request plus the analysis already computed, perform more analysis on the media only when needed, and regenerate the video accordingly. D-056's Context repeats the same four examples in slightly different wording ("insert more photos of Las Vegas", "don't drop Vegas even if low quality", "make the beginning clips 50% longer and shrink the photos around them", "photo duration should rise with the song's tempo") and the ask for "prompt engineering that lets the agent *think* from the request + the analysis present (and re-analyse only when needed) and regenerate the video". Which of the two wordings is closer to what the user typed is not recoverable; the epic was written first, during the session, and D-056 the next day.

### Recorded refinement requests the next day (2026-07-01)

These are recorded as live test requests typed into the running app, not as vision statements, but they are the only other user-worded fragments from the two sessions:

- Pacing: "make the beginning clips 50% longer, shrink the photos around them" (E-2.12 activity log, 2026-07-01; S-2.12.3 acceptance).
- Coverage: "don't drop the Zion shots, lean on landscapes" (S-2.12.3 acceptance).
- Title card: "rename to 'Desert Wandering', move to top, gold, bigger, drop year" (E-2.12 activity log, 2026-07-01).

### The intent behind the instruction (author's reading)

The original 2026-04-25 vision already said the user "is allowed to give input in raw natural language format which the app will just take in and then try to implement again". This instruction makes that concrete against a real output: after the preview the user wants to say anything — coverage, must-keeps, positional clip lengths, tempo-following pacing — and have the product act on it, thinking from what it already knows about the media and analysing more only when it has to, instead of only re-running the story judge with an added hint.

## What was built from it

| Item | What it is | Evidence |
|---|---|---|
| **E-2.11** (done 2026-06-30, PR #67) | S-2.11.1 snappier/fuller edits — Stage 6 per-clip band (photos 1–3 s, video ≥ 2 s, no photo stretching), Stage 4 `video_too_short` eligibility, a judge prompt for ~40–60 clips covering every location+time, a deterministic ≤ 3 clips per ~1 km viewpoint cell — plus T-2.11.1.6 candidate-level cap; S-2.11.2 job- and phase-level feedback; S-2.11.3 per-stage sub-module progress chips; S-2.11.4 `burst_montage` clip kind; S-2.11.5 opt-in AI title/splash card (remote image-gen via `gemini-2.5-flash-image`, cast faces, title + year); S-2.11.6 per-section music mood with music analysis in both modes. | `project/epics/E-2.11-…md` (Children, acceptance, activity log); `project/stories/S-2.11.1-…md` acceptance: verified on the real media at 37 clips (was 17), photo max 2500 ms (was 8000), 14 distinct GPS locations (was ~7), Horseshoe Bend 6 → 3 |
| **S-2.11.7** (PR #69) + **D-055** + **A-026** | AI-written splash-card title from the brief (Tier-S `generate_title_text` op, heuristic fallback); A-026 queues top-locations enrichment. | `docs/decisions/DECISIONS_LOG.md` D-055; `docs/vision/RECOMMENDED_ADDITIONS.md` A-026 |
| **D-054** | The round-2 decisions: duration band, min-video eligibility, judge coverage prompt; remote image-gen for the splash card; the E-2.11 queue. | `docs/decisions/DECISIONS_LOG.md` D-054 |
| **E-2.12** (done 2026-07-01, PRs #72, #73) | **PlanDirective** (ADR-0019, dated 2026-06-30) — one duration/positional/tempo shaping contract consumed by Stage 6 and emitted by refinement; **ReservationSet** (S-2.10.5) — a source-agnostic must-keep set through Stage 4 (the Las Vegas fix, also refinement's force-include path); **S-2.12.3** — `plan_refinement`, one structured call producing a `RefinementOutcome`, and `execute_refinement` rendering a child snapshot; **S-2.12.4** — title-card refinement + re-inject on every refine. Built in the same PR: S-2.10.4 cast cluster merge-pass and S-2.10.6 capture-day stratified budget (ADR-0020, dated 2026-07-01), S-2.10.7 model bump, S-2.10.8 local-embedder interface + stub, S-2.11.5b title-card cost line-item. | `project/epics/E-2.12-…md` (Goal, Children, activity log); `backend/impact_crater/pipeline/stage9_refine.py` — `RefinementOutcome` fields `directive_patch`, `reserve_destinations`, `reserve_refs`, `brief_addendum`, `title_card_patch`, `explanation`; `is_light` routes a pure pacing/title edit to Stage 6 only; the planner prompt lists exactly these five levers |
| **D-056** | The decision to build two shared levers and make the refinement "tools" thin wrappers over them; the multi-turn tool loop deferred. | `docs/decisions/DECISIONS_LOG.md` D-056 |
| **ADR-0019 / ADR-0020** | PlanDirective shared levers; cast cluster merge-pass + stratified Stage-4 budget. | `docs/architecture/ADR-0019-plan-directive-shared-levers.md`, `docs/architecture/ADR-0020-cluster-merge-and-stratified-budget.md` |
| Design record | The six-agent design + synthesis that produced the lever plan (agent output; contains no user text). | `docs/design/refinement_design.json`, promoted from `.scratch/` on 2026-10-24 (S-2.13.6); `docs/design/README.md` |

## What was not built, and where it stands (as of 2026-10-25)

- **The "re-analyse media only when needed" half of the refinement instruction was never built.** `plan_refinement` reasons over the brief, the plan summary, the detected destinations and the music summary; there is no `reanalyze_media` lever and media is never re-analysed on refine. E-2.12's fourth acceptance box is marked superseded by the shipped single-call planner with no tracked item for on-demand re-analysis; S-2.12.3's tool-list box defers the lever to E-4.3.
- **The refinement is one structured call, not the bounded multi-turn tool loop S-2.12.3 was written for** (D-056 Alternatives; S-2.12.3 acceptance). It runs as a single synchronous HTTP call (`api/snapshots.py` `post_refine` awaits `execute_refinement` inline); the async refine job it would need is tracked as S-3.5.5.
- **Three of the four example requests were exercised live; the tempo-aware one only at lever level.** Pacing, coverage and title-card refinements re-rendered child snapshots on 2026-06-30/07-01 (four child snapshots are listed in `docs/roadmap/MVP.md`, pre-flight #8); "increase photo duration with the song's rising tempo" is covered by `tests/test_plan_directive.py::test_tempo_profile_shortens_the_high_energy_half`, not by a live run (E-2.12 acceptance).
- **The round-2 fixes were verified on a cached reconstruction of the SW-US job and on 55-media title-card projects, not on a fresh full-scale run.** No ≥ 900-media job has completed since PR #72 (`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md`, §1 table and §4.5); E-2.10 / E-2.12 acceptance on real output is a restart Phase 3 item.
- **The capture-day stratified budget (S-2.10.6, ADR-0020) is implemented but OFF** behind an A/B flag that no setting reaches (`stage4_prefilter.py`: "(A/B-gated). None → False"). **S-2.10.8** shipped only the pluggable embedder interface and a stub; `build_image_embedder` has no callers in `backend/impact_crater`, and no local model runtime or weights exist.
- **Three large jobs started on 2026-06-30 were lost on a server restart** (in-memory job registry; `LANDSCAPE-AND-PLAN-2026-10-24.md` §1 table; `docs/roadmap/MVP.md` must-do #4) — the persistence gap is S-2.9.19 / A-025; unrelated to the feedback itself but part of that day's record.
- The 2026-06-11 → 2026-07-01 work, including both epics here, is recorded retroactively as the `mvp-hardening` phase (D-057, 2026-10-25).

## Sources

Line numbers are as of master 093946e (2026-10-25) and will drift; the file paths and the quoted strings are the stable anchors.

| Source | Lines | Used for |
|---|---|---|
| `project/epics/E-2.12-open-ended-refinement-and-shared-curation-levers.md` | 17–26 (Goal: the four example requests, "and more we can't predict", the think / re-analyse / regenerate intent); 28–40 (what was delivered); 57–62 (children + PRs); 66–69 (acceptance, incl. the superseded re-analyse box); 78 (the quoted instruction); 79 (the 2026-07-01 title-card request); 80 (the live pacing request; "462 pass") | Part 2; built / not built |
| `project/epics/E-2.11-snappier-edits-output-polish-observability.md` | 17 (Goal); 21–26 (Scope with the #1–#10 mapping); 34–40 (children); 44–47 (acceptance); 60–61 ("round-2 user feedback (10 points → groups A–D)"; "do all"; "419 pass"; PR #67) | Part 1; built |
| `docs/decisions/DECISIONS_LOG.md` | 1156–1164 (D-053: the job, snapshot id); 1166–1174 (D-054: the ten points, remote image-gen chosen by the user, alternatives); 1176–1184 (D-055: the brief text, the heuristic title); 1186–1194 (D-056: the examples re-worded, the two levers, the deferred tool loop, live verification); 1196–1208 (D-057: the mvp-hardening phase) | Parts 1–2; built / not built |
| `project/stories/S-2.11.1-snappier-fuller-edits.md` | 17 (description); 27 (real-media verification numbers); 44–46 (duration-cap rationale; the Group A commits af83d0c + 8eb0a4b named there exist as local objects but are not ancestors of master — PR #67 was squash-merged); 50 | Part 1; built |
| `project/stories/S-2.11.2…S-2.11.7-*.md` | each activity log ("created from feedback #9 / #10 / #5 / #7 / #8"; S-2.11.7 line 36) | the #-mapping; built |
| `project/stories/S-2.12.3-agentic-refinement-loop.md` | 21–33 (acceptance: context load, the deferred tool list incl. `reanalyze_media`, lever routing, the live 2026-07-01 requests); 42–45 (activity) | Part 2; not built |
| `project/BOARD.md` | 7 (the 2026-06-30 "Earlier" summary: "10-point round-2 feedback", "do all") | Part 1 |
| `docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md` | 25 (last build session); 34 (lost 2026-06-30 jobs; no scale run since); 295 (refine verified live, untested); 308; 389 (addenda stop at 2026-06-14; notes folder never created) | why this file exists; not built |
| `docs/roadmap/MVP.md` | 30 (lost jobs); 119 (the four refine child snapshots) | not built / verified |
| `backend/impact_crater/pipeline/stage9_refine.py`; `backend/impact_crater/api/snapshots.py` | 57–87 (`RefinementOutcome`), 226–266 (the planner's levers); `post_refine` at 161–200 | built / not built |
| `docs/architecture/ADR-0019-plan-directive-shared-levers.md`, `docs/architecture/ADR-0020-cluster-merge-and-stratified-budget.md` | headers (dates 2026-06-30 / 2026-07-01) | built |
| `docs/design/README.md`, `docs/design/refinement_design.json` | the README row for `refinement_design.json`; the JSON's `summary` ("Design the intelligent open-ended refinement layer + curation levers (S-2.10.4/5/6/7/8, S-2.11.5/6)") | timeline |
| `git log --since=2026-06-29 --until=2026-07-02` | d4ec922, bba2e13, adcf38d, 4a04ed2, 2bf1f3a, c8a10cc, 4cc0e13, 2bf66b1, 288c46f, da34766 | timeline |
