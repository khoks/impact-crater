# MVP.md — Impact Crater MVP scope

Impact Crater is a dead-simple 1-click media-to-video creator: you dump a pile of photos and videos, describe in your own words the video you want and where to post it, click submit, and the AI does the rest. This document scopes the thinnest end-to-end slice of that one-click experience.

> **Status: MVP scope LOCKED (E-1.4 round 1 closed 2026-05-03).** Product scope locked in E-1.2 (D-006..D-022). Architecture locked in E-1.3 (ADR-0005..0016 / D-023..D-035; 11 novel mechanisms N-001..N-011). Execution roadmap locked in E-1.4 round 1 (9 milestones M0..M9 = E-2.1..E-2.9 under new I-2 MVP; D-036 milestone partition + AI-assisted velocity; D-037 keep all E-1.3 expansions; D-038 code-org sequencing). Velocity = AI-assisted full-time aggressive (user is PM/EM/Architect, Claude does the build via Max 20x plan); estimated calendar 4-8 weeks. **E-1.4 round 2 (ROADMAP.md final lock with v1 / v2 / v3 sequencing) is the next thing on the board after this.**

The MVP is the **single thinnest end-to-end slice** that proves the core loop: *user uploads media → AI curates → user reviews preview → user approves publish*. Everything beyond that thinnest slice goes to v1 or later.

---

## Locked: MVP success criterion (D-014)

> *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes, in their own words, the kind of YouTube video and music they want, picks a target duration, clicks submit, and the AI does the rest — returning a publish-ready **Story Video** to their connected YouTube Studio account within 2–5 hours.*

The user can opt into a refine pass after seeing the rendered result, alongside Approve at the post-render moment (per D-011, D-022 — supersedes the refine-loop half of D-020).

---

## Locked: what the MVP must do

| # | Constraint | Locked by |
|---|---|---|
| 1 | **One artifact type, end-to-end:** Story Video — a single themed video with background music | [D-006](../decisions/DECISIONS_LOG.md), [D-015](../decisions/DECISIONS_LOG.md) |
| 2 | **One platform connector, end-to-end:** YouTube via the user's connected YouTube Studio account | [D-007](../decisions/DECISIONS_LOG.md) |
| 3 | **One LLM routing default, end-to-end:** remote-first; routing abstraction in place from day one so local-first is a v1 config flip, not a rewrite | [D-016](../decisions/DECISIONS_LOG.md) |
| 4 | **Project / job model:** persistent, async, resumable. Closing the laptop and re-opening must restore state | [D-011](../decisions/DECISIONS_LOG.md), [A-001](../vision/RECOMMENDED_ADDITIONS.md), [A-005](../vision/RECOMMENDED_ADDITIONS.md) |
| 5 | **Preview → approve → publish:** approval gate always on, no opt-out. Post-render UI surfaces twin actions: **Approve (primary)** and **Refine this result (secondary)** | [D-020](../decisions/DECISIONS_LOG.md) (publish-approval-always-on half), [D-022](../decisions/DECISIONS_LOG.md) |
| 6 | **Scale envelope:** up to 1000 photos + 50 videos per job, 2–5 hour wall-clock ceiling | [D-012](../decisions/DECISIONS_LOG.md), [D-014](../decisions/DECISIONS_LOG.md) |
| 7 | **Curation pipeline:** hybrid (deterministic pre-filter → multimodal-LLM judgment) with rich per-photo / per-scene metadata; scene segmentation for video | [D-009](../decisions/DECISIONS_LOG.md) |
| 8 | **Music modes:** standard mode (background music) + music-video sub-mode (full version, including section-to-media NL mapping); user-supplied music only at MVP. Beat detection via Madmom; section detection via librosa | [D-010](../decisions/DECISIONS_LOG.md), [D-018](../decisions/DECISIONS_LOG.md), [D-030](../decisions/DECISIONS_LOG.md), [D-031](../decisions/DECISIONS_LOG.md), [A-013](../vision/RECOMMENDED_ADDITIONS.md), [ADR-0012](../architecture/ADR-0012-music-alignment-strategy.md) |
| 9 | **Effort-level UX:** L1–L3 + agentic max-permissible recommendation | [D-013](../decisions/DECISIONS_LOG.md), [A-015](../vision/RECOMMENDED_ADDITIONS.md) |
| 10 | **Internal execution:** a single coordinator with structured tool calls — entirely behind the scenes; the user never sees or configures it | [D-017](../decisions/DECISIONS_LOG.md) |
| 11 | **Mobile posture:** desktop-only at MVP. Mobile is its own v2 epic. (Optional desktop-side cloud-folder watcher is a stretch.) | [D-019](../decisions/DECISIONS_LOG.md) |
| 12 | **Refine loop:** offered post-render alongside Approve as the secondary action; not a job-creation toggle. Per-render, not per-job (every render-complete surfaces the offer again) | [D-011](../decisions/DECISIONS_LOG.md), [D-022](../decisions/DECISIONS_LOG.md) |
| 13 | **Privacy posture:** explicit consent / strip-EXIF / blur-faces controls — load-bearing because remote-first sends images off-device | [A-002](../vision/RECOMMENDED_ADDITIONS.md), [D-016](../decisions/DECISIONS_LOG.md) |
| 14 | **Publishing audit log:** append-only record per project | [A-003](../vision/RECOMMENDED_ADDITIONS.md) |
| 15 | **Cross-job analysis cache (MVP-lite):** universal + model-versioned reuse classes; partial-result reuse → v1 | [A-011](../vision/RECOMMENDED_ADDITIONS.md), [N-007](../vision/NOVEL_IDEAS.md) |
| 16 | **Auto-captions (MVP-lite):** generated at curation; user reviews pre-publish | [A-009](../vision/RECOMMENDED_ADDITIONS.md) |
| 17 | **Per-day spend cap:** hard stop against runaway jobs | [A-004](../vision/RECOMMENDED_ADDITIONS.md) |

The full feature catalog with phase tags lives in [`GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md).

---

## Locked: what the MVP must explicitly NOT do

- Multiple artifact types in one project (only Story Video — D-006).
- Multiple platforms in one publish (only YouTube — D-007).
- Local-first LLM routing default (v1 — D-016).
- Live-job pattern (v1 — A-012, N-005).
- Reference-media style learning (v1 — A-014, N-004).
- Operation-aware LLM router (v1 — N-002, gates the local-first v1 commitment).
<!-- Section-to-media NL mapping inside music-video mode reclassified v1 → MVP per D-031 (2026-05-02). It is now part of constraint #8 above; removed from this not-list. -->
- L4 / L5 effort levels, full cost-transparency UI, upgrade-path agent (v1 — A-015).
- Auto photo / video editing (v1 — per RAW_VISION).
- Multi-version artifact comparison (v1 — A-006).
- Theme library (v1 — A-014 substrate).
- Royalty-free music starter pack and licensed library integration (v1 — D-018).
- Mobile UI (v2 — D-019).
- Multi-agent harness (v2 — D-017).
- Conversational refinement at scale (v2 — D-011, D-017).
- Generated music (v2 — D-018).
- Ultimate Trip Package — the full multi-artifact bundle from one trip (v2/v3).
- Hosted-service mode (v3 — CLAUDE.md mission).

---

## Milestones (M0 → M9)

The MVP execution path is partitioned into **9 milestones**, each mapped 1:1 onto an Epic under the new `I-2 MVP` initiative. Each milestone has a **demoable shipping criterion** (the test that says "this milestone is done"). Effort estimates use the project's standard scale (`S<4h`, `M<1d`, `L<3d`, `XL>3d`) interpreted as **focused-build session-time, not calendar time**, under AI-assisted full-time velocity.

| # | Milestone | Epic | Shipping criterion (the demo) | Effort | Key ADRs / N-NNNs |
|---|---|---|---|---|---|
| **M0** | Scaffolding | [E-2.1](../../project/epics/E-2.1-scaffolding.md) | `pip install impact-crater` works on Windows + macOS + Linux; `impact-crater` CLI starts FastAPI on `localhost`; React shell loads; first-time-setup wizard collects API keys + dual-cap spend caps + Fernet key generation; SQLite schema initializes; the empty app boots cleanly | L | ADR-0005, ADR-0006, ADR-0015 |
| **M1** | Headless curation through Stage 5 | [E-2.2](../../project/epics/E-2.2-headless-curation-through-stage-5.md) | Feed a test set + brief + target_duration via API; get a structured `ArcJudgment` JSON back. `LLMClient` + AnthropicLLMClient + GoogleLLMClient + LLMRouter + telemetry stream + `JobCostSummary` + worker pool all wired up. Pipeline Stages 1–5 working end-to-end **without UI** | XL | ADR-0007, ADR-0009, ADR-0010, ADR-0011, ADR-0015, N-001 |
| **M2** | Render + standard mode | [E-2.3](../../project/epics/E-2.3-render-and-standard-mode.md) | Feed test set + brief + audio + target_duration; get a rendered Story Video MP4 back at YouTube-friendly defaults. Standard music mode (no music-video sync yet, no second-guess yet) | L | ADR-0010, ADR-0012 |
| **M3** | UI MVP loop closed (no YouTube) | [E-2.4](../../project/epics/E-2.4-ui-mvp-loop-closed.md) | User drags media into the React UI, types a brief, picks effort level, sees in-job progress + cost live spend, gets a preview Story Video. Approve / Refine UI buttons present (Approve does nothing yet — no connector; Refine deferred to M6) | XL | ADR-0005, ADR-0011, ADR-0014, ADR-0015 |
| **M4** | Music-video mode + section-to-media NL | [E-2.5](../../project/epics/E-2.5-music-video-mode-and-section-to-media-nl.md) | Madmom + librosa pipeline produces beats + sections + energy curve; tempo-aware beat-grid generated; user's NL section spec ("intro = scenic, chorus = summit") passed to Stage 5; cuts snap to beats in music-video mode | L | ADR-0012, A-013, D-031 |
| **M5** | Person library + face recognition + privacy panel | [E-2.6](../../project/epics/E-2.6-person-library-and-privacy-panel.md) | User adds 3 family members via the face-photo-cropper UI (5 photos each); reference collage builds; **N-008 recognition integrated in Stage 3** with `recognized_persons` field populated in metadata; privacy panel UI live with three toggles + interaction matrix; EXIF/GPS strip + face-blur paths working; **N-011 routing-config schema in place** | XL | ADR-0010, ADR-0016, N-008, N-011 |
| **M6** | Agentic refinement + AI-offered second-guess | [E-2.7](../../project/epics/E-2.7-agentic-refinement-and-second-guess.md) | Internal Stage 9 thinking-step loop with 5 strategies running on the mid-tier model; the AI may *optionally* offer refinements it spotted (`SecondGuessResult`); if it has any, an Apply/Skip/Modify-with-NL UI surfaces them as suggestions the user can accept or ignore before render — never a checkpoint the user must operate; snapshot chain via `parent.txt` per N-003 | XL | ADR-0011, ADR-0014, N-009 |
| **M7** | YouTube publish | [E-2.8](../../project/epics/E-2.8-youtube-publish.md) | OAuth via local-loopback callback works; resumable `videos.insert` (256 MB chunks) uploads a real video to a real YouTube account; publish UI with visibility selector defaulting to public; Approve gate; audit-log writer writes a real entry; **full end-to-end demo: drop photos → curate → preview → approve → published video URL** | L | ADR-0013, A-003 |
| **M8** | Cross-project user profile (N-010 minimum-viable) | [E-2.9](../../project/epics/E-2.9-cross-project-profile-mvp.md) | Feedback log writer hooked into all event sources (approve / refine / second-guess decisions / pre-filter overrides / publish); profile schema persisted at `~/.impact-crater/profile/profile.json`; **deterministic frequency-based derivation at MVP** (LLM-driven re-derivation deferred to post-launch); profile-driven suggestions surface on second-and-later job creation ("based on your past trips, you usually want ~90s videos"); profile reset UI works | L | ADR-0014, N-010 |
| **M9** | Polish + D-014 success-criterion validation | (rolled into E-2.9 acceptance criteria) | Bug fixes + edge-case handling; **the user runs a real 1000-photo + 50-video job from one of their own trips and validates the 2–5 hour ceiling holds, gets a publish-ready Story Video on YouTube within the budget**; documentation polish (README install + first-time-setup walkthrough) | L (build) + open-ended (real-world iteration) | All MVP ADRs |

**Total session-time estimate: ~22–30 days of focused build work** ≈ **4–8 weeks calendar time** at AI-assisted full-time velocity (the lower bound assumes minimal real-world iteration in M9; the upper bound assumes meaningful real-world fixes after M9 begins).

> **Note — Stages 1–9 are internal.** The numbered Stages referenced throughout this document are steps the AI runs automatically behind the user's single click. The user never operates, configures, or steps through them; they may be surfaced as live progress so the user can watch the work happen, but the user never drives them.

The full feature catalog with phase tags lives in [`GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md). Per-epic story / task decomposition happens when each epic opens for work.

---

## Critical-path risks

Five risks are flagged as MVP-critical:

| # | Risk | Mitigation |
|---|---|---|
| 1 | **LLM provider drift during the 4–8 week build window.** Anthropic / Google may change rate cards, deprecate models, or change API surfaces | Pin model versions per ADR-0009 `model_version`; cache invalidation handles model bumps cleanly per N-007; rate cards versioned per `effective_date` per ADR-0015 |
| 2 | **Render performance at MVP scale.** 1000 photos + 50 videos in 2–5 hours requires aggressive worker-pool parallelism | Profile early at M2; tunable concurrency via ADR-0010 worker classes (`cpu` / `ffmpeg` / `network`); effort-level UX (D-013) gives users a way to scope down if their hardware can't hit the ceiling |
| 3 | **Person-library UI complexity (M5).** N-008 is the most novel + UI-intensive piece — face-photo cropper + library management + recognition-confidence-review surface | M5 has the longest single-milestone budget (XL). UI iteration may need extra sessions. The person library is **opt-in** at MVP, so users can ship a Story Video without ever touching it |
| 4 | **Cross-project profile derivation quality (M8).** N-010 is genuinely speculative — does the derived profile actually improve user experience? | M8's deterministic frequency-based derivation is the safe path (no hallucination). LLM-driven re-derivation deferred to post-launch when there's enough feedback log data to validate. Profile reset is a one-click escape hatch if the system suggests bad things |
| 5 | **Claude session bandwidth.** Even with Max 20x, complex sessions can hit context limits or the user's bandwidth | Per-milestone scope is bite-sized (each M is ~1–5 sessions); intermediate commits + branches per milestone; per-milestone PRs auto-merge so master always has the latest stable state; user can resume across sessions |

---

## Pre-flight criteria (declaring MVP done)

I-2 closes — and we exit the MVP phase — when **all** of the following are true:

- [ ] All 9 milestones (E-2.1..E-2.9) closed.
- [ ] **D-014 success criterion verified end-to-end on at least one real user dataset** — the user runs a 1000-photo + 50-video job from one of their own trips, the 2–5 hour ceiling holds, the result is publish-ready, and the user clicks Approve and Publish to a real YouTube account.
- [ ] No critical-bug-class regressions in the curation pipeline (Stages 1–9 all working).
- [ ] Cost-transparency UI shows real numbers under the configured spend caps; both total + per-provider cap enforcement tested.
- [ ] Privacy panel exposes the three toggles correctly with the documented interaction matrix from ADR-0016.
- [ ] YouTube upload flow tested end-to-end on the user's real YouTube account; audit-log entry written; visibility selector tested for all three values (private / unlisted / public).
- [ ] Person library + N-008 recognition tested with at least 3 real persons and at least 50 photos containing them.
- [ ] Refine loop (Stage 9 N-009) tested with at least one real refinement that produces a meaningfully different result.
- [ ] First-time-setup wizard tested as a fresh-install user (delete `~/.impact-crater/`, re-install, walk through wizard, run a job).
- [ ] README install walkthrough tested by a fresh-eyes reader (could be the user re-reading after a week away).
