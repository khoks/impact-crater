# ROADMAP.md — Impact Crater phased roadmap

> **2026-10-25 note.** The phase index and the per-phase sections below were refreshed on 2026-10-25 per [D-057](../decisions/DECISIONS_LOG.md) (S-2.13.4): the MVP's curate→preview half passed on 2026-06-18, its publish half has never executed, 2026-06-11 → 2026-07-01 is recorded as the `mvp-hardening` phase, the I-3 / I-4 / I-5 initiatives already exist, and v1 opens re-sequenced. The audited current state and the phase-wise restart plan (Phases 0–6) live in [`LANDSCAPE-AND-PLAN-2026-10-24.md`](./LANDSCAPE-AND-PLAN-2026-10-24.md) — this file is the phase index, that file is the plan. Text dated before 2026-10-25 is kept as the historical record; amendments are dated inline.
>
> **Status: locked (E-1.4 round 2 closed 2026-05-03).** Five-phase shape + per-phase milestone sequencing all locked. Calendar dates intentionally omitted — phases ship when they ship. Per-phase effort estimates assume **AI-assisted full-time velocity** (the user is PM/EM/Architect; Claude does the build via Anthropic's Max 20x plan) per [D-036](../decisions/DECISIONS_LOG.md). Total path from MVP-start to v3 launch ≈ **12-18 months** at this pace.

Impact Crater is a **dead-simple, 1-click media-to-video creator**: the user dumps a pile of photos and videos, describes the video(s) they want in their own words, clicks submit, and is done — the AI does the rest. Every phase below adds capability *behind* that single action, never on top of it. Local-first models, live jobs, multi-platform publishing, conversational refinement — each makes the one click faster, cheaper, more personal, or more capable, but none of them changes the headline experience the user lives through.

The project moves through five named phases. A phase is a **capability bundle**, not a date. The `phase` frontmatter field on every Initiative / Epic / Story / Task ties the work item to its target phase. The MVP phase is itself partitioned into 9 milestones (M0..M9) tracked under `I-2 MVP`. The later phases have had their own initiatives since 2026-06-14 (`I-3 v1`, `I-4 v2`, `I-5 v3` — created for the in-app workplan tracker and ratified by D-057 on 2026-10-25); their backfilled epic bodies stay one-line placeholders until each epic opens, and the board lists them under "Future phases", not as ready work. The `mvp-hardening` tag (D-057) marks the tail of the MVP initiative — hardening of the shipped single-video product between the gate pass and the formal v1 opening — hosted under I-2 or, where the work outlives the MVP, under I-3.

---

## Phase index

| Phase | Name | Initiative | Status |
|---|---|---|---|
| `scaffolding` | Project foundation | [I-1](../../project/initiatives/I-1-project-foundation.md) | done (2026-05-03) |
| `mvp` | Single thin slice — Story Video → YouTube | [I-2](../../project/initiatives/I-2-mvp.md) | in-progress — curate→preview half of D-014 passed 2026-06-18; closes on the first real YouTube publish (D-057) |
| `mvp-hardening` | Hardening the shipped single-video product between the gate pass and the formal v1 opening | [I-2](../../project/initiatives/I-2-mvp.md) ([E-2.10](../../project/epics/E-2.10-feedback-driven-curation-quality.md) .. [E-2.13](../../project/epics/E-2.13-restart-close-out-and-hygiene.md)) and [I-3](../../project/initiatives/I-3-v1-local-first-live-job-multi-platform-style-polish.md) ([E-3.10](../../project/epics/E-3.10-quality-eval-harness-and-golden-set.md), [E-3.11](../../project/epics/E-3.11-restart-hardening-and-release-engineering.md)) | in-progress since 2026-06-11 (defined 2026-10-24) |
| `v1` | Local-first + live job + multi-platform + style + polish | [I-3](../../project/initiatives/I-3-v1-local-first-live-job-multi-platform-style-polish.md) (exists since 2026-06-14) | in-progress for hardening only — [E-3.3](../../project/epics/E-3.3-multi-platform-connectors-instagram-facebook-x.md) connectors landed dry-run (2026-05-11); E-3.10 eval harness and E-3.11 hardening added 2026-10-24; the formal v1 opening is restart Phase 4 (D-057) |
| `v2` | Mobile + a richer "just talk to the app" experience + generated music | [I-4](../../project/initiatives/I-4-v2-mobile-multi-agent-conversational-generated-music-trip-pa.md) (exists since 2026-06-14) | backlog ([E-4.6](../../project/epics/E-4.6-ai-crowd-removal.md) crowd removal added 2026-10-24) |
| `v3` | Hosted multi-tenant SaaS | [I-5](../../project/initiatives/I-5-v3-hosted-multi-tenant-saas.md) (exists since 2026-06-14) | backlog |

---

## scaffolding (done 2026-05-03)

The project foundation: vision, architecture, work-tracking system, session-housekeeping skills, MVP execution roadmap. **No application code.** All decisions captured as ADRs and `D-NNN` entries; all novel mechanisms in `NOVEL_IDEAS.md`.

Final tally:

- **4 governance ADRs** (ADR-0001 BSL license; ADR-0002 work-tracking hierarchy; ADR-0003 housekeeping skills; ADR-0004 auto-merge policy)
- **12 architecture ADRs** (ADR-0005..0016) covering process topology, storage, LLM stack, media pipeline, curation engine, music alignment, connectors, agent harness, resource accounting, privacy posture
- **39 D-NNN decisions** (D-001..D-039)
- **11 novel mechanisms** (N-001..N-011)
- **15 candidate additions** (A-001..A-015)
- **`MVP.md` placeholder-free** with 9-milestone partition + AI-velocity recalibration + 5 critical-path risks + 10 pre-flight criteria
- **`I-2 MVP` initiative + 9 epic shells** (E-2.1..E-2.9)
- **Two auto-running session-housekeeping skills** (`knowledge-curator`, `work-tracker`) with the auto-merge-with-`--admin` policy

The tally above is the 2026-05-03 scaffolding record and is kept as-is. **Current (2026-10-25):** 21 ADRs (ADR-0001..ADR-0021), 58 decisions (D-001..D-059, with D-058 reserved for the quality-gate decision), 15 novel mechanisms (N-001..N-015), 29 recommended additions (A-001..A-029).

---

## mvp — Single thin slice (4-8 weeks at AI-assisted velocity)

The thinnest end-to-end slice that delivers the core product experience: *the user dumps media, describes the video they want in their own words, clicks submit — the AI curates, the user reviews the preview and approves the publish.* **One artifact (Story Video), one platform (YouTube), one routing default (remote-first).**

The 9 MVP milestones are documented in detail in [`MVP.md`](./MVP.md) §"Milestones." Summary:

| # | Milestone | Epic | Effort |
|---|---|---|---|
| M0 | Scaffolding | [E-2.1](../../project/epics/E-2.1-scaffolding.md) | L |
| M1 | Headless curation through Stage 5 | [E-2.2](../../project/epics/E-2.2-headless-curation-through-stage-5.md) | XL |
| M2 | Render + standard mode | [E-2.3](../../project/epics/E-2.3-render-and-standard-mode.md) | L |
| M3 | UI MVP loop closed | [E-2.4](../../project/epics/E-2.4-ui-mvp-loop-closed.md) | XL |
| M4 | Music-video mode + section-to-media NL | [E-2.5](../../project/epics/E-2.5-music-video-mode-and-section-to-media-nl.md) | L |
| M5 | Person library + privacy panel | [E-2.6](../../project/epics/E-2.6-person-library-and-privacy-panel.md) | XL |
| M6 | AI self-checks and refines its own picks | [E-2.7](../../project/epics/E-2.7-agentic-refinement-and-second-guess.md) | XL |
| M7 | YouTube publish | [E-2.8](../../project/epics/E-2.8-youtube-publish.md) | L |
| M8+M9 | Cross-project profile + polish + D-014 validation | [E-2.9](../../project/epics/E-2.9-cross-project-profile-mvp.md) | L (build) + open-ended (validation) |

*What happened (dated 2026-10-25):* E-2.1..E-2.8 shipped code-complete between 2026-05-03 and 2026-05-05 and E-2.9 on 2026-05-05 (reopened 2026-06-11 for the D-014 validation only); the gate run came six weeks later, on 2026-06-17/18 — see the `mvp-hardening` section below for the numbers.

MVP closes when **the amended `MVP.md` pre-flight is fully ticked** (D-057, 2026-10-25). Of the original wording — *the user runs a real 1000-photo + 50-video job from one of their own trips, the 2-5 hour ceiling holds, and a Story Video is published to their YouTube account* (D-014) — the curate→preview half **passed on 2026-06-18**; the publish half has **never executed**. Exactly one gate is open: **the first real (non-dry-run) private YouTube publish of an existing render through the app, with its audit row** (restart Phase 1 item 4). Every other pre-flight box is either ticked with dated evidence or re-scoped with a date and a tracker ID in `MVP.md`; nothing was silently dropped.

---

## mvp-hardening (2026-06-11 → …) — hardening the shipped single-video product

Not a sixth capability bundle: `mvp-hardening` is the tail of the MVP initiative (D-057; defined in `project/README.md` on 2026-10-24 after being used ad hoc since 2026-06-11). It covers everything between the curate→preview gate pass and the formal v1 opening that hardens the shipped single-video product without adding a user-facing feature class. Hosted under I-2 ([E-2.10](../../project/epics/E-2.10-feedback-driven-curation-quality.md), [E-2.11](../../project/epics/E-2.11-snappier-edits-output-polish-observability.md), [E-2.12](../../project/epics/E-2.12-open-ended-refinement-and-shared-curation-levers.md), [E-2.13](../../project/epics/E-2.13-restart-close-out-and-hygiene.md)) and, where the work outlives the MVP, under I-3 ([E-3.10](../../project/epics/E-3.10-quality-eval-harness-and-golden-set.md), [E-3.11](../../project/epics/E-3.11-restart-hardening-and-release-engineering.md)).

**What shipped 2026-06-11 → 2026-07-01** (all merged to master; the backend suite stands at 477 passing tests on 2026-10-25, 7 real-API integration tests skipped by default):

| Landed | What | Linked |
|---|---|---|
| 2026-06-13 | Preparation-phase overhaul (decided 2026-06-11, D-043; merged in PR #42): capture-time chronology reconciled from EXIF / filename / mtime with confidence + GPS read; rich-metadata enrichment (shot type, per-person expression, specialness, safety, obstructions); cheap-first analysis (1024 px renditions to every vision call, long scenes subdivided); best-of-burst semantic dedup on the embeddings that were already being paid for | D-043, A-016, A-017, A-021, A-022, N-014, S-2.9.5, S-2.9.6 |
| 2026-06-13 | Auto-derived trip cast: unique-face inventory, group-vs-crowd by recurrence breadth, coverage report; face detection made resilient (mediapipe when present, else OpenCV Haar); gemini face-embedding default, insightface optional via `cast_backend` | D-044, A-018, N-012, PR #43 |
| 2026-06-14 | In-app feedback loop: per-phase diagnostics ("Inspect & give feedback"), decision-level correct / incorrect / should-be-different verdicts with a note and a page screenshot, picked up out-of-band by Claude via `scripts/feedback.py`; developer feedback + workplan tracker pages | A-023, A-024, D-045, D-046, D-047, N-015, PRs #44–#46 |
| 2026-06-17 | Token-accurate LLM cost metering from the provider's real usage (the flat per-tier ballpark had undercounted ~5×); credit-exhausted failures surfaced | D-048, S-2.9.14, PR #59 |
| 2026-06-30 | E-2.10 first half + E-2.11: specialness-aware Stage 4 selection; Stage 5 video share / intra-section variety / people-landscape + location balance / strict-forward opener; snappier per-clip duration band (photos 1–3 s, videos ≥ 2 s) with every distinct location + time covered and a per-viewpoint cap; burst-montage clip type; opt-in AI title card with an AI-written title; music mood / section matching in standard mode too; job- and phase-level feedback; richer live module progress; the feedback-modal hang fixed | ADR-0017, D-053, D-054, D-055, S-2.10.1–3, S-2.11.1–7, PR #67 |
| 2026-07-01 | E-2.10 second half + E-2.12: named-destination coverage via `ReservationSet` (the "dropped Las Vegas" fix); trip-cast group gate + cluster merge pass; capture-day stratified Stage 4 budget (implemented, **OFF** behind an A/B flag no setting reaches); `PlanDirective` positional / tempo / soft-align pacing levers; open-ended natural-language refinement as one structured call → a re-rendered child snapshot; title-card refinement + re-injection on refine; model routing bumped to claude-sonnet-4-6 / claude-opus-4-8 (never smoke-tested end to end) | ADR-0019, ADR-0020, D-056, S-2.10.4–7, S-2.12.1–4, PRs #72, #73 |

**The D-014 gate run (2026-06-17/18).** On a real 1,663-asset trip (1,481 photos + 182 videos → 2,067 shots) the pipeline produced a publish-ready 108 s Story Video at confidence 0.85. A 2h55m cold run on 2026-06-17 died on Anthropic credit exhaustion; the 2026-06-18 warm resume took 60 min plus a 9 min render for $18.84; cold-equivalent ≈ 4 h (inside the 2–5 h ceiling), ≈ $50 total for the dataset. That is the **curate→preview half** of D-014.

**What never executed.** The **publish half**: no publish of any kind has run — the audit table is empty, publishing defaults to dry-run (`IC_PUBLISH_DRY_RUN=1`), credentials come from environment variables per `docs/connectors/*.md`, and in-app OAuth was never built. The YouTube, Instagram (container → poll → publish; needs a public HTTPS media URL) and Facebook (Page video) connectors exist in code (PR #34, 2026-05-11); none has been live-tested. Output is 16:9 1080p only. Also not real yet, for the record: the cross-project learning profile (backend + four endpoints, zero event emitters, no UI, never derived); the privacy transforms (strip-EXIF / blur exist as a library with zero call sites; Settings shows read-only hard-coded text; what leaves the machine is a re-encoded 1024 px rendition, unmodified); any on-device model routing (no local LLM runtime exists; every AI call goes to Anthropic or Google); a delete-project / forget-media path.

**How the phase continues — restart Phases 0–3** ([plan §5](./LANDSCAPE-AND-PLAN-2026-10-24.md); D-057):

- **Phase 0 — Resume honestly** (E-2.13, in-progress since 2026-10-24, $0): tracker reconciliation (S-2.13.1, done), D-057 + the honest `MVP.md` pre-flight (S-2.13.2, done), feedback-inbox triage (S-2.13.3, done), this public-trust docs pass (S-2.13.4, done), ADR truth bundle (S-2.13.5, done — ADR-0021 + amendments, D-059, NOTICE / CONTRIBUTING / SECURITY / CODE_OF_CONDUCT / dependabot), repo + session hygiene (S-2.13.6, done), dead-code sweep (S-2.13.7), owner-side $0 model-availability check + Phase 1 spend envelope (S-2.13.8).
- **Phase 1 — Run and publish for real** (E-3.11 plus E-2.8 / E-3.3 items): model-lineup bump to current GA IDs (S-2.10.9); CI on ubuntu + windows (S-3.11.2); local API hardening (S-3.11.3); **the first dry-run and the first real private YouTube publish**; publish-UX honesty; Connect-YouTube-in-Settings (S-3.3.5); publish / refine from any snapshot; closes E-2.9 and I-2; tags v0.1.0.
- **Phase 2 — Instruments + daily-driver hardening** (E-3.10, E-3.11, E-2.9 residuals; $0): the measurable single-video quality gate written down as a decision (D-057 reserves D-058 for it; not yet recorded); the $0 eval harness + owner-labelled golden set (E-3.10, A-029); durable job registry (S-2.9.19); refine as a job (S-3.5.5); mid-job quota guard (S-3.11.1); token-aware estimate (S-2.9.18); privacy-honesty minimum (S-3.1.4); disk / telemetry bounds + a delete path; profile event emitters; test gaps closed.
- **Phase 3 — Single-video quality mastery, then the gate** (paid: 2–3 full runs): a fresh full-scale reference run on the new lineup; root-cause fixes with before/after eval evidence (local visual embedder, two-phase pre-filter, calibrated floors, YuNet detector, cast review, auto-grading, theme presets); the quality-gate run on two real trips, recorded as a further D-NNN (met, or not met with the failing metric). Only a gate-met decision opens Phase 6 (Trip Package pilot + live job); the formal v1 opening is Phase 4.

---

## v1 — Local-first + live job + multi-platform + style + polish (~6 months)

v1 takes the MVP from "single thin slice" to "the differentiated product." Order chosen so that the highest-novelty / highest-differentiation features ship early, polish ships late. Sequencing rationale in [D-039](../decisions/DECISIONS_LOG.md).

> **2026-10-25 (D-057).** The v1.1 → v1.9 *ordering* below is **superseded**; the nine bundles themselves are unchanged. v1 opens re-sequenced per the restart plan: restart Phases 1–3 (first real publish + CI; instruments + daily-driver hardening; single-video quality mastery) run first under two epics added on 2026-10-24 — [E-3.10 quality eval harness + golden set](../../project/epics/E-3.10-quality-eval-harness-and-golden-set.md) and [E-3.11 restart hardening + release engineering](../../project/epics/E-3.11-restart-hardening-and-release-engineering.md) — plus the quality-related v1 stories; then Phase 4 is **publish-and-artifact-first** (E-3.3 connectors → E-3.5 power-user bundle → E-3.8 profile → E-3.7 music → E-3.9 cache → E-3.4 style / E-3.6 auto-editing remainder); **E-3.1 local-first (v1.1) moves to Phase 5** and **E-3.2 live job (v1.2) to Phase 6** behind the D-042 single-video quality gate. I-3 has existed since 2026-06-14 and is `in-progress` for the hardening epics only; a later D-NNN records the formal v1 opening at Phase 4. The table keeps its original numbering as the historical record; each row's epic is named in the Linked column, and rows whose facts changed carry a dated note.

| # | Milestone | What ships | Effort | Linked |
|---|---|---|---|---|
| **v1.1** | **Local-first LLM** | Ollama runtime per ADR-0008 with the ≤32B parameter cap enforced at model-load time; **N-002 operation-aware router** (the cost/capacity-aware resolver replaces the static dict from ADR-0007); **N-011 privacy-sensitive routing becomes functional** (face-data ops actually route to local LLM when blur-faces is ON; was MVP architectural hook); per-operation override UX in settings; v1 hardware-tier mapping (no-GPU / 8-12GB / 16-24GB / 32+GB) per ADR-0008. **2026-10-25:** no on-device runtime exists yet — every AI call goes to Anthropic or Google; the local image-embedder interface (ADR-0018) landed 2026-07-01 as a stub with zero callers and waits for this runtime | 3-4 weeks | E-3.1 (restart Phase 5), ADR-0008, ADR-0018, N-002, N-011 |
| **v1.2** | **Live job (the differentiator)** | A-012 + N-005 — continuous-ingest from cloud-folder watcher (OneDrive / Google Drive desktop-side); **mobile-side camera-roll watcher** (iOS + Android — the v1 first-mobile-touchpoint per D-019); multi-output orchestration from one source set (per-location reels + overall video + collages); during-event publish triggers (schedule-based or user-approval); the user keeps describing what they want in plain language while the job runs and the AI handles it | 4-6 weeks | E-3.2 (restart Phase 6, behind the D-042 gate), A-012, N-005, D-019, D-007 |
| **v1.3** | **Multi-platform: Instagram + Facebook + X** | InstagramConnector (Graph API + Facebook Login); FacebookConnector (Graph API); XConnector (OAuth 1.0a + media upload); per-platform formatting (A-008): 9:16 + 1:1 aspect ratios, per-platform duration caps; multi-platform UI selector per render; watermark / brand-mark mode (A-008) — user-uploaded brand asset, position / size / opacity controls; cross-platform audit log unchanged. **2026-10-25:** the Instagram (Reels: container → poll → publish; needs a public HTTPS media URL) and Facebook (Page video) connectors landed on 2026-05-11 (PR #34) behind env-var credentials and the default-on dry-run flag and have **never been live-tested**; the publish modal offers one platform per publish. Still open: X (S-3.3.4), 9:16 / 1:1 render targets + duration caps + watermark (S-3.3.3 — output is 16:9 1080p only today), Connect-in-Settings (S-3.3.5, restart Phase 1), the first live posts (restart Phase 4). E-3.3 is `in-progress` | 4-5 weeks | E-3.3, D-007, A-008, ADR-0013 |
| **v1.4** | **Reference-media style learning** | N-004 style fingerprint extraction from reference media (color palette, pacing, framing, music feel, narrative shape); theme library (gradually-learned per A-014); style match as a curation objective in Stage 5; reference sources: uploaded files, public URLs (subject to platform ToS), prior projects in the user's library | 3-4 weeks | E-3.4, A-014, N-004 |
| **v1.5** | **Power-user + polish bundle** | A-006 multi-version comparison UI on top of the snapshot graph (ADR-0006); A-007 quality floor calibration + user override (calibrated against MVP usage data); L4-L5 effort levels; A-015 full cost-transparency UI (running spend, trend over time, per-project budgets); N-006 upgrade-path agent (agentic explanation of config changes that unlock higher levels); manual-override (user directly edits `plan.json`) — the deferred-from-MVP failure-mode action; per-image privacy review mode (high-privacy mode prompts on first-send per project); project export with face-library-exclusion option | 3 weeks | E-3.5, A-006, A-007, A-015, N-006, ADR-0014, ADR-0016 |
| **v1.6** | **Auto photo / video editing** | Per-scene auto highlights / shadows / contrast / color grading per RAW_VISION; tunable per project; integrates with Stage 7 render pipeline | 2-3 weeks | E-3.6, RAW_VISION |
| **v1.7** | **Music sourcing expansion** | Royalty-free music starter pack (curated catalog ships in-app); licensed-library integration (Epidemic-Sound-class third-party); conversational section adjustments at chat-refine time ("make the bridge feel more contemplative" — A-013 v1 enhancement). **2026-10-25:** the conversational section adjustments (S-3.7.2) are **partly covered** by the open-ended refinement shipped 2026-07-01 — a single plain-language request can already reshape pacing by position and by music tempo through `PlanDirective` (ADR-0019), and per-section music mood already informs matching (S-2.11.6); what remains is section-specific wording at refine time and the whole music-sourcing half | 2-3 weeks | E-3.7, S-3.7.2, D-018, A-013 |
| **v1.8** | **LLM-driven profile re-derivation** | Replace deterministic-only N-010 (MVP) with Tier-M LLM-driven derivation per ADR-0014; project-tagged feedback so different project types (vacation vs build vs event) derive different priors; per-project temporary profile overrides; explicit "what you've learned" UI surface. **2026-10-25:** the MVP profile backend + four endpoints exist, but zero event emitters, no UI, never derived — emitters are restart Phase 2, the UI half Phase 4 | 1-2 weeks | E-3.8, ADR-0014, N-010 |
| **v1.9** | **Cross-job cache full** | Extend A-011 from MVP-lite (universal + model-versioned reuse classes only) to the full N-007 schema (task-context-specific + time-bounded classes with partial-hit semantics); cache hit-rate dashboard | 1-2 weeks | E-3.9, A-011, N-007 |

v1 closes when all 9 milestones ship and the product visibly distinguishes itself from generic AI-driven media-curation tools via local-first + live-job + multi-platform + reference-style.

---

## v2 — Mobile + a richer "just talk to the app" experience (~3-4 months)

v2 puts Impact Crater in the user's pocket and lets them shape a video by simply talking to the app: the same 1-click dump-and-describe flow on mobile, plus a back-and-forth "more landscape, less faces… make it feel more cinematic" conversation that the AI carries out turn by turn. *Internal note: this conversational depth is enabled by refactoring the AI's single in-job control loop into a coordinated multi-agent harness; that refactor is implementation detail, not a user-facing surface.*

| # | Milestone | What ships | Effort | Linked |
|---|---|---|---|---|
| **v2.1** | **Full mobile UI** | iOS + Android companion app on top of the v1.2 camera-roll-watcher; project list, brief input, in-job progress, preview, approve flow on mobile; the desktop app remains the heavy-lifting host (compute stays on the workstation for now) | 4-6 weeks | E-4.1, D-019 |
| **v2.2** | **Multi-agent harness** | Refactor orchestrator into planner + media-analyst + editor + publisher per the D-017 v2 commitment; per-agent reasoning models tuned via routing-config; coordination protocol; per-agent telemetry classes for ADR-0015. **2026-10-25:** the MVP shipped as a deterministic 9-stage runner with single-shot structured LLM calls — there is no single-orchestrator tool-call loop to refactor; the restart plan first asks (D-NNN) whether the shipped single-call refinement planner suffices | 4-6 weeks | E-4.2, D-017, ADR-0014 |
| **v2.3** | **Conversational refinement at scale** | Chat-style interface for refining ("more landscape, less faces" becomes a multi-turn conversation, not a single message); conversational style adjustments via chat ("make this feel more cinematic" — A-014 v2); the multi-agent harness powers the conversation; bounded session history with profile-derived priors. **2026-10-25:** the *single-request* half shipped on 2026-07-01 — one open-ended natural-language request is mapped by one structured call onto the shared curation levers and re-rendered as a child snapshot (E-2.12); the multi-turn chat and on-demand media re-analysis remain here | 3-4 weeks | E-4.3, D-011, D-017, D-056, A-014 |
| **v2.4** | **Generated music** | Suno-style integration per D-018; cost / quality bounds re-evaluated when committing (Suno's quality keeps improving and we want to commit when bounds are reasonable, not earlier); per-job opt-in | 2-3 weeks | E-4.4, D-018 |
| **v2.5** | **Ultimate Trip Package** | From one dump-and-describe submission, the AI produces a complete set of artifacts for a trip in a single pass — per-location reels, multi-photo albums, a full-journey music-scored video, and montages — bundled together for one preview-and-approve gate; reuses the cross-job analysis cache and person library so the whole package is fast and personal. Opens only on the gate-met D-NNN (D-042 single-video quality gate; restart Phase 6) | 3-4 weeks | E-4.5, RAW_VISION, A-011, A-020, N-013, D-042 |
| **v2.6** | **AI crowd removal** (added 2026-10-24; optional) | Inpaint non-group people out of selected tourist-site photos, using the trip cast's group-vs-crowd split for identity and a person-segmentation mask; pluggable `CrowdRemover` backend — remote image-editing API default, optional on-device LaMa/SDXL-class inpainting for capable machines (D-044); opt-in per photo in the refine loop, never auto-applied, before/after preview, kept beside the originals, disclosed in publish metadata and surfaced under the ADR-0016 privacy posture before first remote use. Not on the critical path; parked behind the Trip Package gate | TBD (opens with Phase 6) | [E-4.6](../../project/epics/E-4.6-ai-crowd-removal.md) (from S-2.9.7), A-019, D-044, N-012, ADR-0016 |

v2 closes when the product is usable on mobile, the "just talk to the app" refinement and generated-music capabilities ship, and the Ultimate Trip Package delivers a full set of trip artifacts from a single submission.

---

## v3 — Hosted multi-tenant SaaS (timing TBD)

v3 is a deployment-mode flip per the project mission (CLAUDE.md): the same codebase runs as a hosted multi-tenant SaaS. Timing depends on go-to-market readiness, not engineering readiness — the architecture (ADR-0006) is designed for this swap.

| # | Milestone | What ships | Effort | Linked |
|---|---|---|---|---|
| **v3.1** | **Hosted infra** | Deployment scaffolding (containerized FastAPI behind a load balancer); object-storage backend (S3-class) replacing per-project filesystem per the ADR-0006 swap-friendly design; Postgres replacing SQLite (the schema transfers unchanged); CDN for the React frontend | 3-4 weeks | ADR-0005, ADR-0006 |
| **v3.2** | **Multi-tenant** | Per-tenant profile storage path per ADR-0014 (the schema anticipates `{tenant_id}/profile.json`); auth (OAuth via Google / Apple / etc); billing (Stripe integration); per-tenant isolation; quota enforcement at tenant level (extends ADR-0015 dual-cap to tenant-cap as a third layer); tenant admin surface | 4-6 weeks | ADR-0014, ADR-0015 |
| **v3.3** | **Public launch** | Landing page; onboarding flow (the first-time-setup wizard becomes a hosted account-creation flow); support ticketing; pricing tiers; status page; legal review (TOS, Privacy Policy aligned with the ADR-0016 privacy posture); BSL 1.1 commercial-use licensing review (revisit the Change Date 2030-04-25 in light of v3 launch timing) | 3-4 weeks | ADR-0001 |

v3 closes when the public launch is live with paying customers.

---

## What's locked vs. what can change

**Locked (won't change without a superseding ADR / D-NNN):**
- The 5-phase shape with `scaffolding` / `mvp` / `v1` / `v2` / `v3` names. **2026-10-25:** D-057 adds the `mvp-hardening` phase *tag* as the tail of the MVP initiative (defined in `project/README.md`), not a sixth capability bundle.
- The `phase` frontmatter field as the authoritative tag for any work item.
- The 9 MVP milestones (M0..M9) per `MVP.md`. **2026-10-25:** the MVP closure criterion is the amended `MVP.md` pre-flight (D-057) — one open gate, the first real YouTube publish.
- The v1 milestone count (9) and the v1.1 → v1.9 ordering, except where re-sequencing decisions land in future D-NNNs (per D-039 the order is the user-accepted recommendation; later observation may justify re-ordering — superseding D-NNNs cover that). **Superseded 2026-10-25:** D-057 is that re-sequencing decision — v1 opens publish-and-artifact-first (E-3.3 → E-3.5 → E-3.8 → E-3.7 → E-3.9 → E-3.4 / E-3.6), local-first (E-3.1) moves to restart Phase 5 and the live job (E-3.2) to Phase 6, and two hardening epics (E-3.10, E-3.11) were added on 2026-10-24; the nine bundles themselves are unchanged.
- The v2 milestone count (5) and ordering. **2026-10-25:** E-4.6 AI crowd removal was added on 2026-10-24 as an optional sixth line (from S-2.9.7, backend shape per D-044), parked behind the Trip Package gate; the ordering of v2.1–v2.5 is unchanged.
- The v3 milestone count (3) and ordering.
- AI-assisted full-time velocity assumption per D-036.

**Can change (with normal grooming + a D-NNN):**
- v1 / v2 / v3 milestone re-sequencing if MVP findings show better orderings.
- Effort estimates per milestone (recalibrate when each milestone actually opens).
- Adding a milestone to v1 / v2 / v3 (e.g., a feature surfaced post-MVP that didn't exist in `RECOMMENDED_ADDITIONS.md` at scaffolding time).
- v3 timing (left intentionally TBD; firms up when v2 closes).

**Calendar dates: intentionally omitted.** Phases ship when they ship. The 4-8 week MVP / 6-month v1 / 3-4 month v2 / TBD v3 estimates are anchors for self-pacing, not commitments.

---

## Where work lives

- **Active and upcoming work** lives in `project/` as Initiatives → Epics → Stories → Tasks, each tagged with the right `phase`. See [`project/BOARD.md`](../../project/BOARD.md) for the live picture.
- **Future-looking ideas** that don't yet have a `project/` item live in [`docs/vision/RECOMMENDED_ADDITIONS.md`](../vision/RECOMMENDED_ADDITIONS.md) and [`docs/vision/GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md). Future grooming sessions convert them into `project/` items at the appropriate phase.
- **Architecture decisions** are in `docs/architecture/` as ADR-NNNN files; **product decisions** are in `docs/decisions/DECISIONS_LOG.md` as D-NNN entries; **novel mechanisms** are in `docs/vision/NOVEL_IDEAS.md` as N-NNN entries.
