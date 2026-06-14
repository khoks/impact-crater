# ROADMAP.md — Impact Crater phased roadmap

> **Status: locked (E-1.4 round 2 closed 2026-05-03).** Five-phase shape + per-phase milestone sequencing all locked. Calendar dates intentionally omitted — phases ship when they ship. Per-phase effort estimates assume **AI-assisted full-time velocity** (the user is PM/EM/Architect; Claude does the build via Anthropic's Max 20x plan) per [D-036](../decisions/DECISIONS_LOG.md). Total path from MVP-start to v3 launch ≈ **12-18 months** at this pace.

Impact Crater is a **dead-simple, 1-click media-to-video creator**: the user dumps a pile of photos and videos, describes the video(s) they want in their own words, clicks submit, and is done — the AI does the rest. Every phase below adds capability *behind* that single action, never on top of it. Local-first models, live jobs, multi-platform publishing, conversational refinement — each makes the one click faster, cheaper, more personal, or more capable, but none of them changes the headline experience the user lives through.

The project moves through five named phases. A phase is a **capability bundle**, not a date. The `phase` frontmatter field on every Initiative / Epic / Story / Task ties the work item to its target phase. The MVP phase is itself partitioned into 9 milestones (M0..M9) tracked under `I-2 MVP`; later phases will get their own initiatives (`I-3 v1`, `I-4 v2`, `I-5 v3`) when they open for work.

---

## Phase index

| Phase | Name | Initiative | Status |
|---|---|---|---|
| `scaffolding` | Project foundation | [I-1](../../project/initiatives/I-1-project-foundation.md) | done (2026-05-03) |
| `mvp` | Single thin slice — Story Video → YouTube | [I-2](../../project/initiatives/I-2-mvp.md) | in-progress (promoted on E-1.4 closure) |
| `v1` | Local-first + live job + multi-platform + style + polish | (I-3, created when v1 opens) | queued |
| `v2` | Mobile + a richer "just talk to the app" experience + generated music | (I-4, created when v2 opens) | queued |
| `v3` | Hosted multi-tenant SaaS | (I-5, created when v3 opens) | queued |

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

MVP closes when **the user runs a real 1000-photo + 50-video job from one of their own trips, the 2-5 hour ceiling holds, and a Story Video is published to their YouTube account** (D-014 + the 10-checkbox pre-flight criteria in `MVP.md`).

---

## v1 — Local-first + live job + multi-platform + style + polish (~6 months)

v1 takes the MVP from "single thin slice" to "the differentiated product." Order chosen so that the highest-novelty / highest-differentiation features ship early, polish ships late. Sequencing rationale in [D-039](../decisions/DECISIONS_LOG.md).

| # | Milestone | What ships | Effort | Linked |
|---|---|---|---|---|
| **v1.1** | **Local-first LLM** | Ollama runtime per ADR-0008 with the ≤32B parameter cap enforced at model-load time; **N-002 operation-aware router** (the cost/capacity-aware resolver replaces the static dict from ADR-0007); **N-011 privacy-sensitive routing becomes functional** (face-data ops actually route to local LLM when blur-faces is ON; was MVP architectural hook); per-operation override UX in settings; v1 hardware-tier mapping (no-GPU / 8-12GB / 16-24GB / 32+GB) per ADR-0008 | 3-4 weeks | ADR-0008, N-002, N-011 |
| **v1.2** | **Live job (the differentiator)** | A-012 + N-005 — continuous-ingest from cloud-folder watcher (OneDrive / Google Drive desktop-side); **mobile-side camera-roll watcher** (iOS + Android — the v1 first-mobile-touchpoint per D-019); multi-output orchestration from one source set (per-location reels + overall video + collages); during-event publish triggers (schedule-based or user-approval); the user keeps describing what they want in plain language while the job runs and the AI handles it | 4-6 weeks | A-012, N-005, D-019, D-007 |
| **v1.3** | **Multi-platform: Instagram + Facebook + X** | InstagramConnector (Graph API + Facebook Login); FacebookConnector (Graph API); XConnector (OAuth 1.0a + media upload); per-platform formatting (A-008): 9:16 + 1:1 aspect ratios, per-platform duration caps; multi-platform UI selector per render; watermark / brand-mark mode (A-008) — user-uploaded brand asset, position / size / opacity controls; cross-platform audit log unchanged | 4-5 weeks | D-007, A-008, ADR-0013 |
| **v1.4** | **Reference-media style learning** | N-004 style fingerprint extraction from reference media (color palette, pacing, framing, music feel, narrative shape); theme library (gradually-learned per A-014); style match as a curation objective in Stage 5; reference sources: uploaded files, public URLs (subject to platform ToS), prior projects in the user's library | 3-4 weeks | A-014, N-004 |
| **v1.5** | **Power-user + polish bundle** | A-006 multi-version comparison UI on top of the snapshot graph (ADR-0006); A-007 quality floor calibration + user override (calibrated against MVP usage data); L4-L5 effort levels; A-015 full cost-transparency UI (running spend, trend over time, per-project budgets); N-006 upgrade-path agent (agentic explanation of config changes that unlock higher levels); manual-override (user directly edits `plan.json`) — the deferred-from-MVP failure-mode action; per-image privacy review mode (high-privacy mode prompts on first-send per project); project export with face-library-exclusion option | 3 weeks | A-006, A-007, A-015, N-006, ADR-0014, ADR-0016 |
| **v1.6** | **Auto photo / video editing** | Per-scene auto highlights / shadows / contrast / color grading per RAW_VISION; tunable per project; integrates with Stage 7 render pipeline | 2-3 weeks | RAW_VISION |
| **v1.7** | **Music sourcing expansion** | Royalty-free music starter pack (curated catalog ships in-app); licensed-library integration (Epidemic-Sound-class third-party); conversational section adjustments at chat-refine time ("make the bridge feel more contemplative" — A-013 v1 enhancement) | 2-3 weeks | D-018, A-013 |
| **v1.8** | **LLM-driven profile re-derivation** | Replace deterministic-only N-010 (MVP) with Tier-M LLM-driven derivation per ADR-0014; project-tagged feedback so different project types (vacation vs build vs event) derive different priors; per-project temporary profile overrides; explicit "what you've learned" UI surface | 1-2 weeks | ADR-0014, N-010 |
| **v1.9** | **Cross-job cache full** | Extend A-011 from MVP-lite (universal + model-versioned reuse classes only) to the full N-007 schema (task-context-specific + time-bounded classes with partial-hit semantics); cache hit-rate dashboard | 1-2 weeks | A-011, N-007 |

v1 closes when all 9 milestones ship and the product visibly distinguishes itself from generic AI-driven media-curation tools via local-first + live-job + multi-platform + reference-style.

---

## v2 — Mobile + a richer "just talk to the app" experience (~3-4 months)

v2 puts Impact Crater in the user's pocket and lets them shape a video by simply talking to the app: the same 1-click dump-and-describe flow on mobile, plus a back-and-forth "more landscape, less faces… make it feel more cinematic" conversation that the AI carries out turn by turn. *Internal note: this conversational depth is enabled by refactoring the AI's single in-job control loop into a coordinated multi-agent harness; that refactor is implementation detail, not a user-facing surface.*

| # | Milestone | What ships | Effort | Linked |
|---|---|---|---|---|
| **v2.1** | **Full mobile UI** | iOS + Android companion app on top of the v1.2 camera-roll-watcher; project list, brief input, in-job progress, preview, approve flow on mobile; the desktop app remains the heavy-lifting host (compute stays on the workstation for now) | 4-6 weeks | D-019 |
| **v2.2** | **Multi-agent harness** | Refactor orchestrator into planner + media-analyst + editor + publisher per the D-017 v2 commitment; per-agent reasoning models tuned via routing-config; coordination protocol; per-agent telemetry classes for ADR-0015 | 4-6 weeks | D-017, ADR-0014 |
| **v2.3** | **Conversational refinement at scale** | Chat-style interface for refining ("more landscape, less faces" becomes a multi-turn conversation, not a single message); conversational style adjustments via chat ("make this feel more cinematic" — A-014 v2); the multi-agent harness powers the conversation; bounded session history with profile-derived priors | 3-4 weeks | D-011, D-017, A-014 |
| **v2.4** | **Generated music** | Suno-style integration per D-018; cost / quality bounds re-evaluated when committing (Suno's quality keeps improving and we want to commit when bounds are reasonable, not earlier); per-job opt-in | 2-3 weeks | D-018 |
| **v2.5** | **Ultimate Trip Package** | From one dump-and-describe submission, the AI produces a complete set of artifacts for a trip in a single pass — per-location reels, multi-photo albums, a full-journey music-scored video, and montages — bundled together for one preview-and-approve gate; reuses the cross-job analysis cache and person library so the whole package is fast and personal | 3-4 weeks | RAW_VISION, A-011 |

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
- The 5-phase shape with `scaffolding` / `mvp` / `v1` / `v2` / `v3` names.
- The `phase` frontmatter field as the authoritative tag for any work item.
- The 9 MVP milestones (M0..M9) per `MVP.md`.
- The v1 milestone count (9) and the v1.1 → v1.9 ordering, except where re-sequencing decisions land in future D-NNNs (per D-039 the order is the user-accepted recommendation; later observation may justify re-ordering — superseding D-NNNs cover that).
- The v2 milestone count (5) and ordering.
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
