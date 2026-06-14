# DECISIONS_LOG.md — Impact Crater chronological decision log

Append-only. Numbered monotonically. See [`README.md`](./README.md) for the format and the difference between decisions, ADRs, and inventions.

---

### D-001 — Project named "Impact Crater" (2026-04-25)

**Status:** accepted

**Context.** The user proposed an AI-driven photo/video curator that turns raw media plus a natural-language brief into ready-to-publish social-media artifacts. A name was needed for the repository, the license, the docs, and the GitHub project URL.

**Decision.** The product is named **Impact Crater**. The GitHub repository slug is `impact-crater`.

**Alternatives considered.** None — the user supplied the name in the original vision.

**Consequences.** Used in the LICENSE Additional Use Grant ("an Impact Crater Service"), in the README, in CLAUDE.md, and in every public artifact going forward. Renaming later is possible but expensive (license, repo URL, prose).

**Linked items.** ADR-0001 (license), GitHub repo `khoks/impact-crater`.

---

### D-002 — License: Business Source License 1.1, Change Date 2030-04-25 (2026-04-25)

**Status:** accepted

**Context.** The user wants free self-hosting for personal / family / team use, but wants to block hosted-service competitors during the early commercial window. They want the code to eventually become permissively open.

**Decision.** License under BSL 1.1 with the *Additional Use Grant* permitting personal / family / team self-hosting and prohibiting hosted-service competition. Change Date is 2030-04-25 (four years from project start). Change License is Apache License 2.0.

**Alternatives considered.**
- *Apache 2.0 from day 1.* Loses the commercial moat. Rejected.
- *All-rights-reserved.* Loses the open-source positioning. Rejected.
- *AGPL.* Doesn't actually block hosted competition. Rejected.

**Consequences.** Must include the LICENSE file at the repo root with the agreed parameters. Any contributor will be subject to BSL 1.1 terms until the Change Date. Forks cannot relicense. On 2030-04-25 (or four years after a specific version's first public release, whichever comes first), the code converts to Apache 2.0 automatically.

**Linked items.** ADR-0001-license.md, [`LICENSE`](../../LICENSE).

---

### D-003 — Work tracking: four-level hierarchy, file-per-item, hierarchical IDs (2026-04-25)

**Status:** accepted

**Context.** The user wants to track Initiatives, Epics, Stories, and Tasks in the repo (not in an external tool), with the ability for a north-star initiative to span multiple sprints' worth of epics. Two shapes were considered: a three-level file-per-item hierarchy and a four-level single-inline-file hierarchy.

**Decision.** Use a four-level hierarchy (Initiative → Epic → Story → Task) with **file-per-item** layout under `project/{initiatives,epics,stories,tasks}/` and **hierarchical IDs** (`I-1`, `E-1.2`, `S-1.2.3`, `T-1.2.3.4`) that never get renumbered.

**Alternatives considered.**
- *Three-level (Epic → Story → Task).* Flattens north-star programs. Rejected — user explicitly named four levels.
- *Four-level inline single file.* Bad for parallel-session merges. Rejected.
- *External tool (GitHub Issues / Jira / Linear).* Loses the offline / clone-and-go ethos. Rejected.

**Consequences.** Templates required for all four levels. The `work-tracker` skill has to scan the relevant subdirectory to allocate the next monotonic ID under a parent. `project/BOARD.md` is hand-maintained (or skill-maintained) as a mirror of frontmatter statuses.

**Linked items.** ADR-0002-work-tracking-hierarchy.md, [`project/README.md`](../../project/README.md).

---

### D-004 — Auto-running session-housekeeping skills with branch-and-PR flow (2026-04-25)

**Status:** accepted

**Context.** Knowledge state and work state generated during a Claude Code session must end up in the repo, not in the chat transcript. The user wants the capture step automated, but wants to retain a review checkpoint by having the changes flow through a pull request rather than land directly on master.

**Decision.** Two project-local skills under `.claude/skills/` — `knowledge-curator` and `work-tracker` — auto-invoked by a `Stop` hook configured in `.claude/settings.json`. Both skills use a strict branch-and-PR flow (branch → commit → push → `gh pr create` against `master`) and **never auto-merge**.

**Alternatives considered.**
- *Direct commits to master.* Faster but no review checkpoint. Rejected.
- *Single combined skill.* Mixes two unrelated concerns. Rejected.
- *Manual invocation only.* Defeats the "automatic" requirement. Rejected.

**Consequences.** Depends on `gh` being installed and authenticated. Depends on `master` being the default branch. PRs accumulate if the user does not review them. Both skills must be no-op-friendly (empty session → no branch, no PR, explicit no-op message).

**Linked items.** ADR-0003-session-housekeeping-skills.md, [`.claude/settings.json`](../../.claude/settings.json), [`.claude/hooks/post-session-housekeeping.sh`](../../.claude/hooks/post-session-housekeeping.sh).

---

### D-005 — GitHub repository public from day 1 (2026-04-25)

**Status:** accepted

**Context.** The user was offered a private-repo option but chose to make the GitHub repository public from the very first commit, prioritizing openness over IP secrecy.

**Decision.** Create the GitHub repo `khoks/impact-crater` with `--public` visibility. Open-source the project from the first commit.

**Alternatives considered.**
- *Private repo to start, public at MVP.* Safer for early-stage IP. Rejected.
- *No GitHub yet, local-only git.* Loses the auto-PR flow that the housekeeping skills require. Rejected.

**Consequences.** Anything committed becomes immediately publicly visible. **Therefore: novel ideas that the user wants to preserve patent options for must be filed in [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md) on a feature branch and discussed with counsel before merging to master.** The `knowledge-curator` skill's PR-only flow gives the user a chance to intercept such ideas before the public-disclosure event of the merge.

**Linked items.** [`README.md`](../../README.md), [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md), GitHub repo `khoks/impact-crater`.

---

### D-006 — MVP critical artifact = single themed video with background music (2026-04-26)

**Status:** accepted

**Context.** The vision in `RAW_VISION.md` enumerates several artifact types (per-location reels, multi-photo posts, montages, full-journey music-scored videos). Round 1 of vision grooming (E-1.2) needed to lock the *single* artifact the MVP renders end-to-end so architecture grooming (E-1.3) and roadmap grooming (E-1.4) can begin from a stable picture.

**Decision.** The MVP renders **one themed video with background music** per job. Not a per-location reel. Not a multi-photo album. One narrative-sequenced video, optionally synced to music, fitting a user-chosen target duration.

**Alternatives considered.**
- *Per-location reel.* Less narratively rich; weaker showcase of the curation engine. Rejected — user explicitly preferred the themed-video shape.
- *Multi-photo album.* Doesn't exercise the video-curation pipeline at all. Rejected — pushes the hard problem to v1.
- *Multiple artifact types in MVP.* Bloats scope. Rejected.

**Consequences.** The MVP renderer must handle scene-segmented video sequencing, music sync (basic for MVP, beat-aligned per A-013/D-010), and a single duration target per job. Per-location reels move to v1. The curation pipeline must produce a *narrative-ordered* output, not just a quality-ranked one — which is what makes N-001 (narrative-arc judgment stage) load-bearing.

**Linked items.** D-007 (YouTube as MVP platform), D-010 (music-video sub-mode), D-014 (success criterion), D-015 (feature name = Story Video), A-001 (project model), [`docs/vision/GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md), [`project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md`](../../project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md).

---

### D-007 — MVP platform = YouTube (2026-04-26)

**Status:** accepted

**Context.** `RAW_VISION.md` lists Instagram, Facebook, YouTube, and X as target connectors. The MVP needs exactly one to keep the publish-gate scope honest.

**Decision.** The MVP publishes to **YouTube** via the user's connected YouTube Studio account. One platform connector, end-to-end.

**Alternatives considered.**
- *Instagram first.* Reels API has tighter scope and shorter duration ceilings; less natural fit for the chosen artifact (themed video, possibly several minutes long). Rejected for MVP.
- *YouTube + Instagram both.* Doubles connector scope. Rejected — second platform moves to v1.
- *Local-only render, no publish.* Breaks the preview-then-approve-then-publish loop that is fundamental per RAW_VISION. Rejected.

**Consequences.** MVP integrates the YouTube Data API v3 for upload + metadata; the explicit-consent gate is wired against YouTube OAuth. Multi-platform publish becomes a v1 feature. Per-platform formatting (aspect ratio, duration ceiling) becomes a v1 concern.

**Linked items.** D-006 (artifact = themed video), A-003 (publishing audit log), [`docs/roadmap/MVP.md`](../roadmap/MVP.md), [`project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md`](../../project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md).

---

### D-008 — Feature must be generically named (not travel-loaded) (2026-04-26)

**Status:** accepted (superseded by D-015 for the actual chosen name)

**Context.** Initial drafts referred to the themed-video feature as "journey video". User flagged that "journey" is too travel-loaded — the input could equally be a build, an event, a project diary, a family milestone, etc. The feature name must work across all those contexts.

**Decision.** The themed-video feature is named with a **generic, context-agnostic noun phrase**. "Journey" and other travel-only framings are explicitly out.

**Alternatives considered.**
- *Journey video.* Travel-only connotation. Rejected.
- *Trip video.* Travel-only. Rejected.
- *Recap video.* Reads past-tense; less natural for live-job futures. Rejected.
- *Memory video.* Family/personal-loaded. Rejected.

**Consequences.** Naming candidates evaluated under O-1 of the round-1 plan. Final selection captured in D-015. All user-facing copy, doc references, and code identifiers must use the chosen generic name.

**Linked items.** D-015 (chosen name), [`project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md`](../../project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md).

---

### D-009 — Curation pipeline = hybrid (deterministic pre-filter + multimodal-LLM judgment) with rich per-photo / per-scene metadata (2026-04-26)

**Status:** accepted

**Context.** Photo/video selection algorithm shape was the central product-design question for the curator. Three candidate shapes existed: pure deterministic pipeline (perceptual-hash → embedding → cluster → quality score → narrative arc), pure multimodal-LLM-as-curator, or hybrid. User chose hybrid and enriched the metadata model substantially.

**Decision.** The curation pipeline is **hybrid**: deterministic pre-filter (dedup, quality floor, scene segmentation) → multimodal-LLM judgment (selection, ordering, narrative arc). On top of that, every photo and every video scene gets a **rich metadata tag set**:

- *Per photo:* time of day, people in focus + identities, lat/long + location description, timestamp, mood, lighting, quality score, foreground + background activity, visible objects (S/M/L size buckets), clothing, pose-quality scores across multiple categories, plus generic tags + user-task-context-specific tags.
- *Per video:* scene-segmented first; each scene gets the per-photo metadata schema applied. File-level metadata also captured: file type, codec, size, duration.

**Alternatives considered.**
- *Pure deterministic pipeline.* Cheap and fast, but cannot judge narrative or context. Rejected — the LLM is what makes the product distinctive.
- *Pure multimodal-LLM-as-curator.* Throws away cheap signals (perceptual hash, EXIF, quality scores) and burns tokens on dedup. Rejected.
- *Hybrid without rich metadata.* Loses the per-media reasoning surface that makes natural-language refinement workable downstream. Rejected.

**Consequences.** The pipeline has explicit boundaries: deterministic stage (CPU-cheap) → metadata-extraction stage (vision-LLM, expensive) → narrative-judgment stage (multimodal-LLM, expensive). The metadata-extraction stage is the load-bearing cost driver and the natural target for the operation-aware router (N-002). Scene segmentation becomes a first-class pre-step for video. The narrative-judgment stage is what N-001 covers as a candidate novel mechanism. Cross-job reuse of computed metadata is what A-011 / D-011-adjacent N-007 covers.

**Linked items.** D-016 (remote-first MVP routing, since rich metadata extraction at scale needs remote VLMs to hit 2–5 hr ceiling), N-001 (narrative-arc judgment stage), N-002 (operation-aware router), N-007 (cross-job cache schema), A-011 (cross-job cache), [`project/tasks/T-1.2.1.2-curation-pipeline-metadata-model.md`](../../project/tasks/T-1.2.1.2-curation-pipeline-metadata-model.md).

---

### D-010 — Music-video mode in scope as a sub-mode of the themed-video feature (2026-04-26)

**Status:** accepted

**Context.** RAW_VISION mentions music-scored videos. User clarified that two distinct modes exist: *standard mode* (selected/generated background music plays under the curated video) and *music-video mode* (the result is synced as a music video around the user's supplied music + theme). User also wants natural-language section-to-media mapping inside music-video mode.

**Decision.** Both music modes are in scope for the Story Video feature:
- **Standard mode** ships in MVP. Music plays under the curated narrative-ordered video.
- **Music-video mode** ships in MVP as a *sub-mode*, with basic beat-alignment and section-to-media sync. The richer **natural-language section-to-media mapping** (user describes which sections of the music should be built from which media) ships in v1.

**Alternatives considered.**
- *Music-video mode is a separate feature.* Forces two parallel orchestrators. Rejected — same job-creation flow, same render pipeline.
- *Music-video mode is v1-only.* Pushes a distinctive product capability out of MVP. Rejected — basic beat-alignment is cheap once the renderer exists.
- *Section-to-media mapping in MVP.* Requires natural-language understanding of music structure plus per-section curation querying. Defer to v1.

**Consequences.** The Story Video render pipeline must accept user-supplied music (per D-018) and respect basic beat boundaries when sequencing. The job-creation conversation must capture which mode the user wants. Section-to-media mapping needs music-structure analysis (intro/verse/chorus/bridge detection) plus a curation-query interface — both v1.

**Linked items.** D-018 (music sourcing), A-013 (music-video output mode), [`project/tasks/T-1.2.1.3-music-modes-sourcing.md`](../../project/tasks/T-1.2.1.3-music-modes-sourcing.md).

---

### D-011 — Job model = async; refine-loop opt-in; publish-approval gate always on (2026-04-26)

**Status:** accepted

**Context.** Curation runs at MVP scale (D-012: 1000 photos + 50 videos, 2–5 hour ceiling) cannot expect the user to sit and wait. The product needs a model where the user can configure a job, leave the app, and return when it's done. The refine-loop and approval-before-publish gates are user-facing controls that must have explicit defaults.

**Decision.**
- **Jobs are async.** User configures a Story Video job (input media, brief, music, duration, mode), submits, and is free to leave. The app processes in the background, persists state, and resumes after sleep / reboot / network blip (per A-005).
- **Publish-approval gate is always on.** Per RAW_VISION ("only after explicit user approval publishes"). Not user-toggleable. Foundational to the product.
- **Refine-loop is opt-in at job creation, default OFF.** Most users want a clean output the first time; refine is for power users.

**Alternatives considered.**
- *Synchronous, blocking jobs.* Forces user to babysit; collapses on long jobs. Rejected.
- *Publish-approval as opt-out.* Breaks the trust model that defines the product. Rejected.
- *Refine-loop default ON.* Forces every user through an extra step. Rejected.

**Consequences.** Storage layer must persist job state durably (input refs, intermediate metadata, candidate set, ordering, render artifact). Resume logic must be testable (A-005 failure-recovery). UI must show running jobs and let users return to them. Refine-loop becomes a Story Video feature flag at job-creation; no MVP refine UI required if refine is OFF, but the architecture must allow it (per the conversational-refinement v2 commitment).

**Linked items.** D-012 (scale), D-014 (success criterion), D-020 (refine-loop default), A-001 (project/job model), A-005 (failure-recovery / resume), [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### D-012 — MVP scale target = 1000 photos + 50 videos / 2–5 hour wall-clock ceiling (2026-04-26)

**Status:** accepted

**Context.** The MVP must commit to a concrete scale envelope so the architecture (E-1.3) can size compute, memory, and storage; and so the success criterion (D-014) is testable.

**Decision.** A single MVP Story Video job processes **up to 1000 photos + 50 videos**. End-to-end wall-clock time, from job submission to publish-ready preview, must not exceed **2–5 hours** on the routing default (D-016: remote-first).

**Alternatives considered.**
- *Smaller envelope (e.g. 100 photos / 5 videos).* Easy to hit but unrepresentative of "thousands of photos from a trip" use case in RAW_VISION. Rejected.
- *Larger envelope (e.g. 10000 photos / 500 videos).* Unrealistic for MVP under any routing default; that's L5 in the effort-level UX (D-013). Rejected — pushed to v1.
- *No wall-clock ceiling.* Hides the cost of bad routing decisions. Rejected.

**Consequences.** The architecture must hit ~2 photos/sec aggregated across the metadata-extraction stage, or roughly that throughput on video scenes (assuming ~10 scenes per video → ~500 scenes total). Remote-first (D-016) is what makes this plausible at MVP. Local-first cannot meet this on a single laptop GPU and is therefore deferred to v1 (gated on N-002 operation-aware router). The 2–5 hr ceiling becomes a hard test for the MVP success criterion (D-014).

**Linked items.** D-013 (effort-level UX — L1..L3 sit inside this envelope; L4..L5 exceed it), D-014 (success criterion), D-016 (remote-first routing default), A-004 (cost / quota dashboard), [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### D-013 — Effort-level UX with agentic max-permissible recommendation (2026-04-26)

**Status:** accepted

**Context.** The user can plausibly throw anything from 10 photos to tens of thousands at the app. A single "scale" knob is too coarse; absolute photo counts are too cryptic. The product needs a **levelled UX** that translates user intent + hardware/quota reality into an actionable recommendation.

**Decision.** Define **3–5 effort levels** (e.g. L1 ≈ 10 photos + 1 short video; L5 ≈ 10000 photos + 500 long videos). Based on the user's LLM config (local model class, remote provider quotas, local/remote split), the app **computes the max permissible level** and surfaces it after task details + media selection. Three regimes:
- *Within max permissible:* job runs at the requested level.
- *Beyond max permissible but within possible:* cost is shown transparently; user must confirm.
- *Beyond what the current config can support at all:* app explains the upgrade path in LLM settings (which provider tier, which local model class, what changes).

The recommendation, cost-explanation, and upgrade-path UX are **agentic + GenAI-generated**, not static templated copy.

**Alternatives considered.**
- *Single "scale" slider with absolute photo count.* Too cryptic; doesn't explain cost or feasibility. Rejected.
- *Hard cap per tier with no explanation.* Wastes the LLM's ability to explain itself. Rejected.
- *No upgrade-path coaching.* Leaves users stuck with no path forward. Rejected.

**Consequences.** L1..L3 ship in MVP with the max-permissible recommendation. Full **cost-transparency UI** and the **upgrade-path agent** ship in v1 (require deeper integration with provider billing APIs and a maintained model-cost catalog). The recommendation engine is the MVP's first real "agent surface" — sets a precedent for how the orchestrator (D-017) talks to the user. The effort-level packaging itself is a candidate novel mechanism (N-006).

**Linked items.** D-012 (scale envelope sets L1..L3 boundaries), D-016 (routing default constrains the calculus), D-017 (single orchestrator hosts the recommendation), A-015 (effort-level UX as feature entry), N-006 (novel mechanism), A-004 (cost / quota dashboard), [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### D-014 — MVP success criterion (2026-04-26)

**Status:** accepted

**Context.** "The MVP works" must be testable, not aspirational. RAW_VISION's loop is *user uploads → AI curates → user reviews preview → user approves publish*; this needs to be tightened into one user-facing sentence that fixes inputs, outputs, and time.

**Decision.** **MVP success criterion (verbatim):** *User drops up to 1000 photos and 50 videos from a single trip / build / event, describes in a paragraph what kind of YouTube video they want and what kind of music, picks a target duration, and gets a publish-ready video to their connected YouTube Studio account within 2–5 hours.* The user can opt into a refine-and-approve gate before publish (per D-011, D-020).

**Alternatives considered.**
- *Smaller envelope success criterion.* Doesn't represent the real-world use case. Rejected.
- *Quality-floor success criterion (e.g., "Net Promoter Score ≥ N on the output").* Not testable at MVP without users. Rejected — quality testing belongs to a later phase.

**Consequences.** Every E-1.3 architecture decision is judged against whether it lets us hit this sentence. Every E-1.4 roadmap-cut is judged against whether it preserves this sentence. Acceptance test for MVP is a single end-to-end run that meets this criterion on a representative laptop with the user's configured remote-LLM provider.

**Linked items.** D-006, D-007, D-010, D-011, D-012, D-013, D-016, D-017, D-018, D-019, D-020, [`docs/roadmap/MVP.md`](../roadmap/MVP.md), [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### D-015 — Feature name = "Story Video" (2026-04-26)

**Status:** accepted (supersedes the working name "journey video"; resolves D-008)

**Context.** D-008 ruled that the feature name must be generic across travel / build / event / project / family. Six candidates were proposed in O-1 of the round-1 grooming plan: Story Video, Recap Video, Highlights Video, Chronicle, Memory Video, Showcase Video.

**Decision.** The themed-video feature is named **Story Video**. A music-video-mode instance is a "Music Story Video" (per D-010 sub-mode). A future live-job (per A-012) is a "Live Story Video".

**Alternatives considered.**
- *Recap Video.* Reads past-tense; awkward for live-job futures. Rejected.
- *Highlights Video.* Slight sports/action connotation. Rejected.
- *Chronicle.* Distinctive but less searchable; weaker pairing with "music" and "live" qualifiers. Rejected.
- *Memory Video.* Family/personal-loaded; weaker for build/project framing. Rejected.
- *Showcase Video.* Portfolio/build-loaded; weaker for travel/family framing. Rejected.

**Consequences.** All user-facing copy, doc cross-references, and code identifiers use **Story Video**. The job-creation flow asks the user to set up a Story Video job. The render pipeline produces a Story Video artifact. Live-job and music-video qualifiers prepend cleanly.

**Linked items.** D-006, D-008, D-010, A-013, [`docs/vision/GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md), [`project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md`](../../project/tasks/T-1.2.1.1-mvp-artifact-platform-naming.md).

---

### D-016 — LLM routing default for MVP = remote-first (2026-04-26)

**Status:** accepted

**Context.** RAW_VISION commits to a hybrid local/remote LLM design with per-user routing. The MVP must pick **one** default so the architecture is concrete; the routing abstraction must exist either way so the other mode is a config flip in v1, not a rewrite.

**Decision.** **Remote-first** is the MVP routing default. The routing abstraction is in place from day one. Local-first arrives in v1, gated on the operation-aware router (N-002) so cheap operations (perceptual hash, dedup, EXIF parsing) can stay local while expensive operations (rich metadata extraction, narrative-arc judgment) keep using remote VLMs.

**Alternatives considered.**
- *Local-first MVP.* Aligns better with a privacy-by-default brand; honest for users without remote-API access. **Costs us speed to market** — D-009's rich metadata model on D-012's scale envelope (1000 photos + 50 videos) cannot hit D-014's 2–5 hr ceiling on a single laptop GPU running 7B–32B vision models. Rejected for MVP; revisited as v1 default once N-002 lands.
- *No default; user picks at install.* Forces a config decision before the user has any context. Rejected.

**Consequences.** MVP requires the user to bring a remote-LLM API key (Claude, GPT-4o, Gemini, or equivalent). Privacy posture (A-002) becomes a first-class MVP concern because images leave the device by default. The cost-transparency UI (A-004) becomes more important because remote-first means real per-job dollar cost. Local-first remains a v1 commitment, not a maybe.

**Linked items.** D-009, D-012, D-014, D-019 (mobile posture), N-002 (operation-aware router), A-002 (privacy posture), A-004 (cost / quota dashboard), [`project/tasks/T-1.2.1.5-routing-harness-mobile-posture.md`](../../project/tasks/T-1.2.1.5-routing-harness-mobile-posture.md).

---

### D-017 — Agent harness shape for MVP = single orchestrator with structured tool calls (2026-04-26)

**Status:** accepted

**Context.** Two harness shapes were on the table: single-orchestrator-with-tools, or multi-agent (planner + media-analyst + editor + publisher). The agentic UX of D-013 (effort-level recommendation, cost explanation, upgrade pathing) and the future conversational refine loop both need a clear ownership story.

**Decision.** **Single orchestrator** with structured tool calls in MVP. The agentic UX is a *layer on top* of the orchestrator, not a multi-agent backend. Multi-agent (planner + media-analyst + editor + publisher) is a v2 commitment, gated on the conversational editing dialogue landing at scale.

**Alternatives considered.**
- *Multi-agent in MVP.* Gives flexibility we don't yet need; adds debug pain (cross-agent state, message-passing, orchestration-of-orchestrators). Rejected for MVP.
- *No orchestrator; plain function pipeline.* Loses the ability to deliver the agentic recommendation/explanation surface. Rejected.

**Consequences.** All sub-operations in the curation pipeline (perceptual-hash, embedding, scene-segment, metadata-extract, narrative-judge, render, publish) are exposed to the orchestrator as **tools** with structured schemas. The operation-aware router (N-002) plugs into the tool dispatch layer. The conversational refine loop, when it lands, can be implemented by extending the orchestrator's tool set without restructuring. Multi-agent migration in v2 happens by carving the orchestrator's tool groups into specialist sub-agents.

**Linked items.** D-013 (agentic recommendation lives here), D-016 (routing plugs into tool dispatch), N-002 (operation-aware router), [`project/tasks/T-1.2.1.5-routing-harness-mobile-posture.md`](../../project/tasks/T-1.2.1.5-routing-harness-mobile-posture.md).

---

### D-018 — MVP music sourcing = user-supplied only (2026-04-26)

**Status:** accepted

**Context.** Music-video mode (D-010) already requires the user to supply music. Standard mode (background music under the curated video) needs a sourcing decision: user-supplied, royalty-free starter pack, licensed library integration, or generated.

**Decision.** **User-supplied music only** in MVP. The user provides the audio file (or a URL the app can download from); the app does not ship its own catalog or integrate a third-party catalog at MVP. A small **royalty-free starter pack** and **licensed-library integration** ship in v1.

**Alternatives considered.**
- *Royalty-free starter pack in MVP.* Adds catalog curation, licensing review, and a content-management UI. Rejected — pushes scope.
- *Licensed-library integration in MVP (e.g., Epidemic Sound API).* Adds vendor onboarding, billing pass-through, attribution rules. Rejected — pushes scope.
- *Generated music (e.g., Suno-style) in MVP.* Compounds remote-API cost and adds a quality variable we can't yet bound. Rejected — possibly v2.

**Consequences.** The MVP UI asks the user to drop in a music file. The user is responsible for music licensing on their own uploads (matches YouTube's content ID model — D-007). Standard mode and music-video mode share the same user-supplied input pathway. The royalty-free pack and licensed integration become two separate v1 features.

**Linked items.** D-007 (YouTube as platform — its Content ID model is what makes user-supplied workable), D-010 (music-video mode), A-013 (music-video output mode), [`project/tasks/T-1.2.1.3-music-modes-sourcing.md`](../../project/tasks/T-1.2.1.3-music-modes-sourcing.md).

---

### D-019 — Mobile posture for MVP = desktop-only (2026-04-26)

**Status:** accepted

**Context.** RAW_VISION nods at mobile but doesn't require it. Live-job (A-012) is the feature that most strongly implies a mobile-side watcher (camera-roll source). Since A-012 is v1, the mobile question for MVP is open.

**Decision.** **MVP is desktop-only.** Ingest = local folder pick + drag-drop. Optionally, a OneDrive / Google Drive folder watcher as a stretch (cleanly desktop-side, no mobile app required). Mobile app is its own **v2 epic**.

**Alternatives considered.**
- *Mobile-first MVP.* Forces the live-job (A-012) infrastructure to land in MVP (continuous ingest + cloud watcher + during-event publish). Rejected — pushes 2–5 hr ceiling into 2–5 weeks.
- *Mobile companion in MVP (status-only viewer).* Adds an entire app-store / build-pipeline dimension for marginal user value. Rejected.

**Consequences.** MVP runs on Windows / macOS / Linux desktop. The app's UI is a desktop UI (web stack or native; tech-stack choice belongs to E-1.3). Live-job's mobile camera-roll watcher is part of the v1 A-012 scope. Camera-roll watcher as the v1 first-mobile-touch-point is what justifies mobile as its own v2 epic rather than a tacked-on MVP afterthought.

**Linked items.** D-012 (scale envelope assumes desktop GPU), D-016 (routing default), A-012 (live-job pattern, v1), [`project/tasks/T-1.2.1.5-routing-harness-mobile-posture.md`](../../project/tasks/T-1.2.1.5-routing-harness-mobile-posture.md).

---

### D-020 — Publish-approval gate always on; refine-loop opt-in default OFF (2026-04-26)

**Status:** superseded by [D-022](#d-022) (2026-04-28) for the refine-loop half. The publish-approval-always-on half remains in force.

**Context.** D-011 set the job model's coarse shape (async, refine-loop opt-in, publish-approval always on). This decision pins the user-facing defaults precisely so the MVP UI design has nothing to negotiate.

**Decision.**
- **Publish-approval gate is ALWAYS ON. No opt-out, ever.** The user *must* preview and approve the rendered Story Video before it leaves the app to YouTube. This is foundational per RAW_VISION ("only after explicit user approval publishes").
- **Refine-loop is opt-in at job creation, default OFF.** Most users want a clean first-pass output; the refine UI is for power users and adds a step in the happy path. Refine is a per-job toggle (set at job-creation time), not a global setting.

**Alternatives considered.**
- *Publish-approval as opt-out for "trusted" outputs.* Erodes the trust model; opens a path for accidental publishes. Rejected.
- *Refine-loop default ON.* Forces every user through an extra confirmation step. Rejected.
- *Refine-loop as a global setting.* Confuses per-job intent. Rejected.

**Consequences.** The MVP UI must always render the preview-and-approve screen between render-complete and YouTube upload. The publish action is a deliberate user click, never an automatic step. The refine toggle appears at job creation alongside mode (standard vs. music-video) and effort level (D-013); when OFF, the post-render UI is preview → approve → publish. When ON, the post-render UI inserts a refine pass between preview and approve.

**Linked items.** D-011, D-014, A-006 (multi-version artifact comparison — only valuable when refine is on), [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md).

---

### D-021 — All Claude-generated PRs auto-merge with `--squash --delete-branch` (2026-04-26)

**Status:** accepted (supersedes the "never auto-merge" clause of D-004 / ADR-0003)

**Context.** D-004 / ADR-0003 established that the `knowledge-curator` and `work-tracker` skills open a PR against `master` and never merge it — the user reviews and merges by hand. After running the flow once end-to-end (E-1.2 round 1 closure, session a974bff1), the user concluded the manual-merge step adds friction without adding value at this phase: the PR diff is reviewable inside the session as the changes are made (every Edit / Write tool call is visible live), the PR description and per-commit messages already capture the audit trail, and merged PRs remain fully revertible with `gh pr revert` / `git revert`. Branches accumulate when PRs sit waiting, polluting `gh pr list` and the GitHub branches view.

**Decision.** **All Claude-generated PRs auto-merge by default**, immediately after opening, with `gh pr merge <N> --squash --delete-branch`. This applies to:

1. `knowledge-curator` PRs (docs).
2. `work-tracker` PRs (project tracking).
3. **Feature PRs** opened from any future development session.

The user's verbatim directive (2026-04-26): *"PRs should be automerged be it the work tracker or knowledge curator or actual work PRs."*

The branch-and-PR flow itself stays — no direct commits to `master`. Conventional Commits messages still required. Hooks still run. No `--no-verify`. Merge strategy is `--squash` (linear master history, one-commit-per-PR) and `--delete-branch` (clean `gh pr list`).

**Alternatives considered.**
- *Auto-merge only for housekeeping skills; manual merge for feature PRs.* Splits the model: contributors have to learn which PRs auto-merge and which don't. Rejected — the user explicitly named feature PRs in the directive.
- *Auto-merge with a CI gate.* Sound long-term, but no CI is configured at this phase. Rejected for now; revisit when CI lands (likely E-1.3 or first feature work).
- *Use `--merge` (preserve per-commit history on master) instead of `--squash`.* Preserves more context but bloats master history with WIP / fix-typo commits as sessions evolve. Rejected — squash is cleaner for one-PR-per-coherent-change flow.
- *Use `--rebase` for linear no-merge-commits history.* Equivalent to squash for single-commit PRs but worse for multi-commit PRs (preserves intermediate commits without the squash hygiene). Rejected.
- *Hold the original "never auto-merge" stance.* Costs friction the user concluded was redundant. Rejected.

**Consequences.**
- The two SKILL.md files and the `post-session-housekeeping.sh` hook block-reason are updated to describe the new flow.
- ADR-0003 status header is updated to point to ADR-0004; ADR-0003's "never auto-merge" decision-list bullet is rewritten to reflect the supersession.
- CLAUDE.md "Decisions locked" row for skill git autonomy is updated; the "Things to never do" list drops the "Merge an auto-generated PR" line and adds two stricter rules (no direct commits to master; no `--merge` / `--rebase` on the auto-merge step).
- `gh pr list` stays empty between sessions; master is the canonical state at every session end.
- The in-session conversation transcript becomes the authoritative review log — the user's directives + the model's reasoning + each Edit / Write tool call form the record. No second-pass async review.
- A bad change can land immediately, mitigated by the same revert path that always existed plus the user's right to say "hold this PR open" mid-session for high-stakes changes.
- Branch protection on `master` cannot require external code review under this model. Acceptable at this phase; revisit when the project has more than one human contributor.

**Linked items.** D-004 (the originally-decided "never auto-merge" stance, now superseded), [`docs/architecture/ADR-0003-session-housekeeping-skills.md`](../architecture/ADR-0003-session-housekeeping-skills.md) (status header updated), [`docs/architecture/ADR-0004-skill-pr-auto-merge.md`](../architecture/ADR-0004-skill-pr-auto-merge.md) (the formal ADR for this decision), [`.claude/skills/work-tracker/SKILL.md`](../../.claude/skills/work-tracker/SKILL.md), [`.claude/skills/knowledge-curator/SKILL.md`](../../.claude/skills/knowledge-curator/SKILL.md), [`.claude/hooks/post-session-housekeeping.sh`](../../.claude/hooks/post-session-housekeeping.sh), `CLAUDE.md`, project items E-1.5 / S-1.5.1 / T-1.5.1.1.

---

### D-022 — Refine-loop is offered post-render, not toggled at job creation (2026-04-28)

**Status:** accepted (supersedes the refine-loop half of [D-020](#d-020); the publish-approval-always-on half of D-020 stays in force)

**Context.** D-020 (2026-04-26) pinned the refine-loop default as *opt-in at job creation, default OFF*: the user toggles refine ON/OFF when they create the job, then either flows through the refine UI or skips straight to approve after render. On reviewing the round-1 grooming output (2026-04-28), the user redirected the UX shape: instead of asking the user to make a decision *before* they have any information about the output, the app should render the result first and then **offer the refine option alongside the final result**. The user's verbatim direction: *"the refine loop could be an optional thing proposed to the user in the end with the final result."*

This is a UX-shape change, not a scope change — the refine functionality itself is still in MVP, the publish-approval gate is still always on, and the underlying job-model durability requirements (D-011) are unchanged.

**Decision.** **The refine-loop is offered to the user after the rendered Story Video is shown, not as a per-job toggle at job-creation time.** Concretely:

1. **Job creation** no longer asks about refine. Mode (standard vs. music-video — D-010, A-013), effort level (D-013), target duration (D-014), and music input (D-018) remain the only at-creation knobs.
2. **Post-render UI** is now: render-complete → preview-and-approve screen (D-020 publish-approval half) with **two clear actions**: (a) "Approve and publish" — the happy-path, one-click action; and (b) "Refine this result" — the opt-in route that takes the user into the refine UI and produces a new candidate version (the multi-version comparison surface in A-006 becomes natural here once it lands in v1).
3. **Refine is still optional, not mandatory.** Most users will click Approve on the first result; the refine button is the second-place action, visually clear but not pre-selected and not blocking.
4. **Refine is per-render, not per-job.** Every render-complete event surfaces the offer. A user who refines once gets a new render and the same offer again on the new result.

**Alternatives considered.**
- *Keep D-020 as-is (toggle at job creation).* Forces the user to predict whether they'll want to refine *before* they've seen anything. Adds a decision point at the worst time (information-poor moment). Rejected per user redirect.
- *Refine always-on, skip-button to approve.* Functionally equivalent in flow, but signals "we expect you to refine" which biases the user into extra work. Rejected — Approve should be the visually primary action.
- *Refine offered only when a quality / confidence heuristic flags the result as low-confidence.* Sound long-term, but requires a calibrated quality model that is itself v1 work (A-007). Rejected for MVP — re-evaluate when A-007 lands.
- *Hide refine behind a settings toggle the user opts into.* Adds a settings-management surface for a feature that should be discoverable from the result. Rejected.

**Consequences.**
- **MVP UI.** Job-creation form drops the refine toggle. Post-render UI gains a second action button ("Refine this result") next to Approve. The refine UI itself is unchanged in scope from D-020; only the entry point moves.
- **D-011 narrative is unchanged** — the job model is still async, refine is still opt-in (just opt-in *later*), and the publish-approval gate is still always on.
- **D-014 (success criterion) is unchanged in wording** — the criterion already says "user can opt into a refine-and-approve gate before publish." The interpretation is now "opt-in at the post-render moment" rather than "opt-in at job creation," which is consistent with the verbatim text.
- **A-006 (multi-version artifact comparison)** becomes the natural UX home for showing original-vs-refined renders. A-006 stays v1, but the MVP refine UI should produce the version-graph data structure A-006 will consume.
- **Architecture impact** is minimal — N-003 (project as a versioned artifact) already implies every render is a node and refine produces a new node. The change is purely the user-facing entry point.
- **Linked work-items.** T-1.2.1.4 (job model + scale + success criterion + effort levels) gets a same-day-redirect activity-log entry. The story S-1.2.1 and epic E-1.2 stay `done` — the original decisions were captured correctly and are being refined here, not reopened.

**Linked items.** D-011 (job-model frame), D-014 (success criterion — wording unchanged), [D-020](#d-020) (superseded for the refine-loop half), A-006 (multi-version comparison — natural home for refined renders), N-003 (project as versioned artifact — substrate), [`docs/vision/GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md) (Refine-loop row updated), [`docs/roadmap/MVP.md`](../roadmap/MVP.md) (constraints updated), [`project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md`](../../project/tasks/T-1.2.1.4-job-model-scale-success-criterion.md) (activity log appended).

---

### D-023 — Process topology + language stack: Python/FastAPI backend, TypeScript+React frontend, pip-install packaging (2026-04-28)

**Status:** accepted (formalized in ADR-0005)

**Context.** The MVP critical path needs to mix deterministic media operations (ffmpeg, OpenCV, perceptual hashing, scene segmentation) with LLM-driven curation, on a desktop-only target (D-019), as a self-hosted-first install. The CV/ML ecosystem the project depends on is Python-first; the UI surface (D-020 / D-022 preview-and-approve with twin Approve+Refine actions) is browser-first and TypeScript+React-shaped.

**Decision.** Backend = Python 3.11+ with FastAPI (async, websocket support). Frontend = TypeScript + React, served as static assets from the FastAPI process. Heavy lifting = Python subprocess workers spawned by the orchestrator, with an in-process queue at MVP. Packaging = `pip install impact-crater` + `impact-crater` CLI command that starts the local server and opens the browser. Single primary process; no separate frontend server in production.

**Alternatives considered.**
- *Node-everything (TypeScript backend).* CV/ML ecosystem is materially weaker; would subprocess Python anyway → net more complexity. Rejected.
- *Tauri / Electron native frontend.* Browser UI is sufficient for MVP; native chrome can bolt on later as a packaging-only change. Deferred.
- *Rust + Python.* Premature optimization; LLM calls + ffmpeg are the bottleneck, not perceptual-hash speed. Rejected for MVP.
- *Go backend.* Same CV/ML disadvantage as Node, plus weaker LLM SDKs. Rejected.
- *CLI-only (no UI server).* Doesn't fit the preview-and-approve UX. Rejected.

**Consequences.** Single-language backend; one pip install + one command for end users; async-first I/O; subprocess workers managed by the orchestrator; native frontend later is a packaging change, not a rewrite; v1 local LLMs plug into the same Python process via ADR-0008's slot; v3 hosted-service is a Postgres-swap config flip.

**Linked items.** ADR-0005, D-014 (success criterion), D-016 (routing default), D-017 (orchestrator), D-019 (desktop-only), D-020 + D-022 (preview-approve + refine UX), N-003 (project as versioned artifact substrate), A-005 (failure recovery), [`project/tasks/T-1.3.1.1-adr-0005-process-topology-language-stack.md`](../../project/tasks/T-1.3.1.1-adr-0005-process-topology-language-stack.md).

---

### D-024 — Storage layout: per-project tree under ~/.impact-crater, SQLite metadata, content-hash-referenced source media (2026-04-28)

**Status:** accepted (formalized in ADR-0006)

**Context.** The project / job model (D-011, A-001), versioned-artifact substrate (N-003), cross-job cache (A-011, N-007), failure recovery (A-005), and audit log (A-003) all need a coherent storage shape. Source media is large at MVP scale (10s of GB per D-012); copying it into projects would waste disk.

**Decision.** Per-project tree under `~/.impact-crater/projects/{project_id}/` with `manifest.json`, `sources/` (JSON sidecars), `snapshots/{snapshot_id}/` (immutable per-render directories with `plan.json`, `metadata/`, `candidates/`, `render.mp4`, `parent.txt`), `renders/`, `cache/`. SQLite at `~/.impact-crater/db/impact-crater.sqlite` for metadata (projects, media, project_media, snapshots, audit, settings, cache_index). Source media referenced by `(source_path, content_hash=SHA-256)`, not copied. Cross-project cache at `~/.impact-crater/cache/{content_hash}/{provider}_{model}_{version}/...`. Append-only JSONL audit log at `~/.impact-crater/audit.jsonl` (mirrored in the SQLite `audit` table for query convenience). All paths overridable via `IMPACT_CRATER_HOME`.

**Alternatives considered.**
- *Copy source media into the project.* Doubles disk usage; portability gain not worth it for MVP. Rejected (revisit pin-to-project as a post-MVP option).
- *Postgres / server database.* Deployment dependency. Rejected for MVP; v3 hosted-service swaps Postgres in.
- *No projects/ subdivision (single global store).* Breaks N-003 cleanly. Rejected.
- *JSON-on-disk instead of SQLite.* Doesn't scale to A-011 cache lookups. Rejected.
- *Pure content-addressed object-store layout.* Over-engineered for desktop MVP; users expect "my project is a folder" mental model. Rejected for MVP.
- *Embed cache inside per-project tree (no cross-project cache).* Loses A-011 reuse. Rejected.

**Consequences.** Source-path moves trigger content-hash fallback search at re-open (matches Lightroom/Photos UX). Snapshots are immutable; refine produces a new snapshot. Cache key = content-hash + provider + model + model-version + operation = exactly N-007's schema. Audit log is append-only out-of-band JSONL for crash safety. Schema migrations are Alembic-driven once code lands. v3 hosted-service mode swaps disk → object storage and SQLite → Postgres; schema transfers unchanged.

**Linked items.** ADR-0006, ADR-0005, A-001, A-003, A-005, A-010, A-011, N-003, N-007, D-011, D-012, [`project/tasks/T-1.3.1.2-adr-0006-storage-layout.md`](../../project/tasks/T-1.3.1.2-adr-0006-storage-layout.md).

---

### D-025 — Remote-LLM abstraction = LLMClient protocol; MVP providers = Anthropic + Google (2026-04-28)

**Status:** accepted (formalized in ADR-0007)

**Context.** D-016 commits to remote-first MVP with the routing abstraction in place from day one. The user's E-1.3 redirect (2026-04-28): at least two providers at MVP so the abstraction is exercised under more than one shape; user accepted Anthropic + Google.

**Decision.** Single `LLMClient` Python `Protocol` with typed async methods per operation (`embed_image`, `caption_image`, `extract_metadata_image`, `score_image`, `caption_video_scene`, `extract_metadata_video_scene`, `judge_narrative_arc`, `parse_user_brief`, `recommend_effort_level`, `explain_cost`, `explain_upgrade_path`, `tool_call`, `stream_chat`). MVP implementations: `AnthropicLLMClient` (`anthropic` SDK) and `GoogleLLMClient` (`google-generativeai` SDK). Routing dispatch = a static YAML config at `config/llm-routing.yaml` mapping `Operation -> (Provider, Model)`. The v1 N-002 operation-aware router replaces this static dict with an agentic resolver against the same `Operation` taxonomy. Failure model: structured retry + hard ceiling, raise `LLMOperationFailed` on permanent errors. Observability: every call emits `LLMCallEvent` to `telemetry.jsonl` (consumed by ADR-0015 / A-015 cost-transparency UI). Caching: read-through against the `cache_index` table per ADR-0006 with cache key = sha256(content_hash + provider + model + model_version + operation + prompt_version + params_canonical).

**Alternatives considered.**
- *Single-provider MVP (Anthropic only).* Doesn't validate abstraction is genuinely pluggable. Rejected per user redirect.
- *Three-plus providers at MVP.* Marginal value over two; deferred to v1.
- *Single fat `call_llm(operation, ...)` method.* Loses structured-output type safety. Rejected.
- *LangChain.* Costs control over prompt-versioning / caching / observability. Rejected.
- *Per-call provider override.* Caller-side provider knowledge defeats abstraction. Rejected.
- *No protocol — duck typing only.* Loses static type checking. Rejected.
- *Separate `EmbeddingsClient`.* Embeddings are just another operation. Rejected.

**Consequences.** Adding a third provider in v1 is one new file. The static routing dict is the seed for the v1 agentic resolver — no call-site changes when N-002 lands. Async-only with explicit sync wrappers at boundaries. Embeddings normalized as `numpy.ndarray (D,) float32`. Each provider has its own auth (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`); single-provider degraded mode supported with UX warning. Prompt templates versioned in `prompts/{operation}/{provider}_{model}.jinja2`; prompt_version is a hash of template content. Structured-output ops reject schema mismatches (catches provider drift). Cost estimation is provider-specific with versioned rate cards.

**Linked items.** ADR-0007, ADR-0005, ADR-0006, D-016, D-017, D-009, D-013, A-004, A-015, A-007, N-001, N-002, [`project/tasks/T-1.3.1.3-adr-0007-remote-llm-abstraction.md`](../../project/tasks/T-1.3.1.3-adr-0007-remote-llm-abstraction.md).

---

### D-026 — Local-LLM runtime slot (architecture-only at MVP); v1 candidate Ollama (2026-04-28)

**Status:** accepted (formalized in ADR-0008; runtime selection deferred to v1)

**Context.** D-016 commits to remote-first MVP with v1 adding a local-first config flip. The local-LLM landscape (Ollama, llama.cpp, vLLM, ExLlamaV2, MLX) is moving fast; locking the runtime now risks committing before the v1 N-002 router findings inform the choice. The 32B parameter cap is from CLAUDE.md mission.

**Decision.** A `LocalLLMClient` slot in the same provider registry as the remote clients (ADR-0007). MVP ships the slot as an empty stub with `NotImplementedError`-raising methods that document the contract. Routing config maps no operations to `provider: local` at MVP. Hardware detection is v1. Recommended v1 runtime: **Ollama** (single-binary, OpenAI-compatible API, pull-by-name model management, cross-platform, active community). Alternatives kept open until v1: llama.cpp Python bindings (finer control), vLLM (best throughput, server-class), MLX (Apple Silicon). v1 hardware-tier mapping placeholder: no-GPU → remote-only; 8–12 GB → ≤7B local for Tier-S; 16–24 GB → up to 13B local for Tier-S, sometimes Tier-M; 32+ GB → up to 32B local for Tier-S + Tier-M; Tier-L always remote (no ≤32B model meets Opus-class quality reliably). 32B cap enforced at model-load time as a hard refusal.

**Alternatives considered.**
- *Lock the runtime now (Ollama at MVP).* Premature; v1 N-002 findings should inform the choice. Rejected.
- *No local slot in MVP.* Breaks D-016's "abstraction in place from day one" and forces a v1 refactor. Rejected.
- *Local as a deployment toggle without abstraction.* Parallel call sites for local vs. remote — exactly what D-016 forbids. Rejected.
- *Multiple local clients (one per runtime) at MVP.* Premature; pick one in v1, add others as registry entries later. Deferred.
- *No 32B cap enforcement at the runtime layer.* Pushes policy into config / docs / CI — weaker. Rejected.

**Consequences.** v1 work is "implement `LocalLLMClient` + ship the runtime + extend routing config" — no protocol or call-site changes. N-002 router is the v1 unit of work for splitting ops between local and remote. Hardware detection is v1. 32B cap is hard-enforced at model load. Multiple local runtimes can coexist in the registry. MVP startup does not touch any local runtime.

**Linked items.** ADR-0008, ADR-0007, ADR-0005, ADR-0006, D-016, A-015, N-002, CLAUDE.md mission, [`project/tasks/T-1.3.1.4-adr-0008-local-llm-runtime-slot.md`](../../project/tasks/T-1.3.1.4-adr-0008-local-llm-runtime-slot.md).

---

### D-027 — Cost-tiered per-operation model lineup at MVP: Tier-S Gemini Flash, Tier-M Sonnet 4.7, Tier-L Opus 4.7 (2026-04-28)

**Status:** accepted (formalized in ADR-0009)

**Context.** Per the user redirect (2026-04-28), cost-tiering applies across every LLM operation, not only the vision call. At MVP scale (1000 photos + 50 videos per job), bulk-op cost compounds: a Sonnet-class model on bulk captioning is ~30× the cost of Flash for marginally-better one-line captions. The savings on bulk fund a heavier model (Opus) on the one operation where reasoning quality genuinely matters: narrative-arc judgment (N-001).

**Decision.** Three cost tiers with a per-operation static routing table:

- **Tier-S** (cheapest, bulk) = Gemini 2.5 Flash. Used for high-volume low-stakes-per-call ops: caption_image, score_image, caption_video_scene.
- **Tier-M** (mid, structured) = Claude Sonnet 4.7. Used for structured-output ops + agentic UX prose + the orchestrator's tool-call loop: extract_metadata_image, extract_metadata_video_scene, parse_user_brief, recommend_effort_level, explain_cost, explain_upgrade_path, orchestrator_reasoning.
- **Tier-L** (heavy reasoning) = Claude Opus 4.7. Used for one-call-per-job heavy ops: judge_narrative_arc.
- Embeddings (image + text) = Google text-embedding-004 (or current Google embedding model at session time) — separate from the S/M/L axis.

Routing config = `config/llm-routing.yaml` (a flat `operation: {provider, model}` map), loaded by the `LLMRouter` (ADR-0007). Per-user overrides via SQLite settings table (ADR-0006). Per-job overrides via the effort-level UX (D-013): always-Opus / always-Flash / per-op-select. The v1 N-002 router replaces the static lookup with an agentic resolver against the same Operation taxonomy.

Per-job MVP cost envelope estimate (rough): $7–22 USD per full-scale job before A-011 cache hits.

**Alternatives considered.**
- *One model for everything (Sonnet across the board).* ~30× cost overhead on Tier-S calls. Rejected per user redirect.
- *Anthropic-only with Haiku for bulk.* Loses multi-provider abstraction validation; Gemini Flash is at-or-below Haiku cost at MVP-relevant quality. Rejected.
- *Always-Opus for the orchestrator.* Orchestrator runs ~20–80 turns per job; per-call cost compounds. Sonnet sufficient for tool dispatch. Rejected.
- *Per-operation model picks made by the user upfront.* Too much UX complexity for MVP; effort-level overrides cover the cases that matter. Rejected.
- *Cost-tier as a runtime parameter (cheap mode / quality mode) rather than per-op static.* Black-box quality slider; loses per-op rationale. Rejected.
- *Use Gemini 2.5 Pro for mid-tier instead of Sonnet.* Sonnet's structured-output and tool-use reliability more proven at session time. Rejected; revisit in v1 with eval data.
- *Skip cost-transparency UI at MVP.* A-015 says it's MVP scope. Out of scope here.

**Consequences.** Per-job cost is bounded by the table; A-004 per-day cap consumes the telemetry. v1 N-002 router replaces the static dict. Adding a new operation = update ADR-0009 + config + prompt template. Cache hits are highest on Tier-S + embedding ops (content-keyed); Tier-M re-uses on unchanged metadata; Tier-L always re-runs (per-job inputs). The 32B local-tier (v1) replaces only Tier-S calls (and selectively Tier-M); Tier-L stays remote because no ≤32B model meets Opus-class quality reliably as of session time. Single-provider degraded mode routes everything to the available provider with a UX warning.

**Linked items.** ADR-0009, ADR-0007, ADR-0008, D-009, D-013, D-016, D-017, N-001, N-002, N-006, A-004, A-007, A-011, A-015, [`project/tasks/T-1.3.1.5-adr-0009-cost-tiered-model-lineup.md`](../../project/tasks/T-1.3.1.5-adr-0009-cost-tiered-model-lineup.md).

---

### D-028 — Media pipeline framework: Pillow + pillow-heif + rawpy + ffmpeg + imagehash + scenedetect + smartcrop.py; person-library face recognition via reference collage (2026-05-02)

**Status:** accepted (formalized in ADR-0010)

**Context.** The deterministic media-handling layer (decoders, perceptual hash, scene segmentation, face detection, smart-crop, render execution) needs concrete library picks. Two MVP-relevant nuances surfaced in round-2 grooming: HEIC/RAW support is required because iPhone is HEIC-default; face *recognition* (not just detection) significantly enriches narrative-arc judgment, and the user proposed a novel approach (N-008) to avoid carrying a separate face-recognition stack.

**Decision.** Photo decode = Pillow + pillow-heif + rawpy; working colorspace at metadata extraction = sRGB; EXIF via pyexiv2. Video decode = ffmpeg via ffmpeg-python; scene-representative frames extracted as PNG, no full re-encode at analysis. Thumbnails = 256 + 1024 px JPEG cached at ingest. Perceptual hash = imagehash (pHash + dHash). Dedup posture = off-by-default with surfaced suggestion. Scene segmentation = scenedetect ContentDetector with 50/video cap. Smart-crop = smartcrop.py with face-bbox bias. Aspect ratios at MVP = 16:9 only (YouTube). Render = in-process ffmpeg, max-1-concurrency at MVP.

**Face recognition (N-008 architectural realization):** vision LLM is the only face stack; person library in SQLite (`persons` + `person_face_photos` tables, default 5 photos/person, 3-10 range); reference collage constructed at recognition time and passed as second image input to `extract_metadata_image`; structured-output schema gains `recognized_persons` field with confidence scores. Cache key includes `library_version_hash` for correct invalidation.

**Worker pool:** asyncio task pool with cpu/ffmpeg/network worker classes; backpressure surfaced via job-progress websocket; cancellation via `JobCancelled` propagation; resume reads snapshot's `plan.json`.

**Alternatives considered.**
- *Skip HEIC at MVP.* Rejected — iPhone is HEIC-default; manual conversion is hostile UX.
- *Skip RAW at MVP.* Considered. rawpy adds one dep, unlocks power-user segment. Accepted.
- *Auto-remove duplicates at ingest.* Rejected — hostile UX.
- *InsightFace / FaceNet / DeepFace for face recognition.* Rejected — heavy dep, separate model file, doesn't integrate with LLM-driven metadata stage. N-008 collage approach achieves same outcome with zero new dependencies.
- *GPU-accelerated perceptual hashing.* Premature; CPU is fast enough at MVP scale.
- *Container-isolated render (Docker sidecar).* Rejected at MVP — packaging burden; revisit at v3 hosted-service.
- *moviepy / imageio* for video orchestration. Rejected — higher overhead, less encoder control than ffmpeg-python.

**Consequences.** HEIC + RAW deps in the install path (both pip-installable wheels). Person library = UI surface needing design work; SQLite schema locked here. Cache invalidation around library is non-trivial; library_version_hash on cache key keeps it correct. Reference collage bounded to ~20 persons (pagination = v1 enhancement). Scene-count cap (50/video) constrains long-form footage; effort-level UX raises it. Render concurrency (max 1) is conservative; revisit if testing shows render is the bottleneck. Privacy posture (A-002) interactions are formalized in ADR-0016.

**Linked items.** ADR-0010, ADR-0005, ADR-0006, ADR-0007, ADR-0009, D-009, D-012, D-019, A-002, A-005, A-010, A-011, A-015, **N-008** (novel mechanism), [`project/tasks/T-1.3.2.1-adr-0010-media-pipeline.md`](../../project/tasks/T-1.3.2.1-adr-0010-media-pipeline.md).

---

### D-029 — Curation engine = 9-stage pipeline with floor/ceiling pre-filter, orchestrator second-guess (with user reconfirm), and agentic refinement (2026-05-02)

**Status:** accepted (formalized in ADR-0011)

**Context.** D-009 fixed the high-level hybrid shape; N-001 surfaced narrative-arc judgment as the load-bearing mechanism. Round-2 grooming surfaced three user-redirected behaviors: pre-filter must respect a floor + ≤80% ceiling; refine pass should be agentic (orchestrator chooses partial fix vs full reprocess vs additional input — N-009); orchestrator can second-guess the judge but must reconfirm with the user before applying overrides.

**Decision.** Pipeline = 9 stages: (1) ingest + content-hash + scene-segment + thumbnails (deterministic); (2) bulk per-asset ops — embed + caption + score (Tier-S + embedding); (3) rich metadata extraction with N-008 person recognition (Tier-M); (4) pre-filter — quality + dedup + cluster + rank → candidate set; (5) narrative-arc judgment producing structured `ArcJudgment` (Tier-L Opus, single call); (6) plan compilation + orchestrator second-guess + music alignment (deterministic + Tier-M); (7) render (ffmpeg); (8) preview UI with twin Approve/Refine; (9) agentic refinement (N-009).

**Stage 4 floor + ceiling math:** floor = max(50, target_duration_seconds × 2); ceiling = floor(input_count × 0.80); default_target = clamp(input × 30%, floor, ceiling). User overrides via effort-level UX, hard-capped within [floor, ceiling].

**Stage 6 orchestrator second-guess:** Tier-M sanity-check call produces `SecondGuessResult` with proposed `Override`s + confidence; if non-empty AND confidence > 0.6, surface to user via websocket; user picks Apply / Skip / Modify-with-NL per override; choices persist on snapshot.

**Stage 9 refinement (N-009):** Tier-M tool-call loop with tools `re_run_stage_5_with_addendum`, `re_extract_metadata_for`, `re_run_pre_filter_with_overrides`, `request_user_input`, `explain_why_not_possible`. Bounded at 10 turns. Cancelable. Most refinements re-run Stages 5–7; bulk Stage 2/3 cost reused. Cost envelope per refinement ~$1–5 USD vs $7–22 for full job (per ADR-0009).

**Cache reuse story:** Stages 1–3 typically cached on re-run + on refine; Stage 5 always re-runs on refine (refinement message changes input); Stage 6/7 always re-run.

**Alternatives considered.**
- *Skip Stage 4 pre-filter.* Tier-L would drown at 1000 photos. Rejected.
- *Skip orchestrator second-guess.* Rejected per Q7 — small valuable safety net.
- *Always second-guess silently (no user reconfirm).* Rejected — breaks trust model.
- *Refine = simple Stage-5-rerun with parent ArcJudgment.* Round-1 proposal version. Rejected per Q6 — user wants agentic plan generation.
- *Refine = full reprocess always.* Wastes cache. Rejected.
- *Brief-aware narrative-relevance in Stage 3 instead of Stage 2.* Kept in Stage 2; cheap Tier-S call suffices.
- *Quality floor fixed (no user override).* User wedding photos vs summit-attempt photos have different floors. Made overridable.
- *Stage 6 LLM-driven (not deterministic).* Kept deterministic for predictability; second-guess is the LLM hook.

**Consequences.** Stage 5 = highest-cost LLM call (Tier-L Opus, 1/job); cache key wide-enough-but-narrow-enough. Stage 6 user-prompt UI surface needed (post-round-3 design work). Stage 9 bounded at 10 turns. N-009 is novel-mechanism-class. Brief-change invalidates narrative-relevance scores. Snapshot persists orchestrator-override decisions for v1 learning. The 9-stage shape is canonical; v1 features (A-006/007/014) plug into specific stages without reshaping.

**Linked items.** ADR-0011, ADR-0005, ADR-0006, ADR-0007, ADR-0009, ADR-0010, D-009, D-011, D-013, D-014, D-016, D-017, D-022, A-001, A-005, A-006, A-007, A-011, A-013, A-014, A-015, **N-001** (narrative-arc judgment — Stage 5), **N-008** (face recognition via collage — Stage 3), **N-009** (agentic refinement — Stage 9), [`project/tasks/T-1.3.2.2-adr-0011-curation-engine.md`](../../project/tasks/T-1.3.2.2-adr-0011-curation-engine.md).

---

### D-030 — Music alignment: Madmom for beats + librosa for sections; agentic duration mismatch handling; full A-013 NL section-mapping in MVP (2026-05-02)

**Status:** accepted (formalized in ADR-0012)

**Context.** D-010 fixed two music modes (standard, music-video). D-018 fixed user-supplied music at MVP. A-013 originally classified section-to-media NL mapping as v1; round-2 grooming pulled it into MVP per Q10. Beat-detection accuracy materially affects music-video-mode quality; per Q8 user picked Madmom over librosa. Per Q9 duration mismatch handling is agentic at runtime, not a fixed default.

**Decision.** Audio ingest = ffmpeg-decoded to 22050 Hz mono WAV for analysis. Music structure analysis = Madmom (RNN-based beat + downbeat detection) + librosa (sections via `librosa.segment.agglomerative` + RMS energy curve via `librosa.feature.rms`). `MusicAnalyzer` abstraction makes the libraries swappable; MVP implements `MadmomLibrosaAnalyzer`.

**Beat-grid generation:** default cut every 4 beats (1 bar at 4/4); tempo-adjusted (slow → 2-bar; fast → 2-bar to keep clips reasonable); section-boundary snapping if cut would land within 200ms of boundary; user override via effort-level UX.

**Section-to-media NL mapping (A-013 in MVP):** the user's free-text spec ("intro = scenic, chorus = summit") is a first-class input to Stage 5 (narrative judge, ADR-0011) — passed verbatim alongside brief + music structure to the Tier-L Opus call. No structured-parse stage; the judge handles the prose natively. `ArcJudgment.section_mapping` is the structured output.

**Music duration mismatch handling = agentic at runtime (Q9):** Tier-M `analyze_music_duration_mismatch(music, target_duration) → DurationStrategy` tool call. Strategies: `fade_out`, `loop_with_crossfade`, `truncate_at_section`, `loop_then_truncate`. Orchestrator's reasoning considers section boundaries, loopability, target_duration deviation. Strategy + rationale recorded on snapshot and surfaced via cost-transparency UI.

**Render-time alignment:** standard mode = audio under entire video at -16 LUFS; music-video mode = cuts snap to `CutGrid.cut_points_ms`; two-pass `loudnorm` for YouTube-friendly loudness on both modes.

**Alternatives considered.**
- *librosa for beat detection only.* Convenient but materially lower accuracy than Madmom for music-video cuts. Rejected per Q8.
- *BeatNet or other recent beat detector.* Considered as fallback; `MusicAnalyzer` abstraction makes swap trivial. Not chosen at MVP — Madmom's accuracy is well-known and stable.
- *Fixed default for duration mismatch (always fade-out).* Rejected per Q9 — different combinations want different strategies.
- *Loop infinitely under long target.* Boring; rejected as default.
- *Section-to-media NL parsed into structured sections at job creation.* Rejected — Tier-L judge handles prose natively; structured parse is unnecessary intermediate work.
- *Section-to-media NL deferred to v1 (original A-013 classification).* Rejected per Q10 — full version is one prose field, no architectural debt.
- *Royalty-free starter pack widening in MVP.* Out of scope; D-018 holds.

**Consequences.** Madmom is heavier dep with C extensions; pre-built wheels exist for common platforms but edge cases may need attention; `MusicAnalyzer` abstraction is insurance against Madmom maintenance friction. librosa section labels are heuristic; user's NL spec grounds placement. `analyze_music_duration_mismatch` joins the orchestrator's tool surface (formalized in ADR-0014 round 3). Section-to-media NL is one extra textarea at job creation, optional. Two-pass loudnorm adds ~10s to render time. **A-013 reclassification (v1 → MVP) recorded as D-031** and propagated into GROOMED_FEATURES.md + MVP.md + RECOMMENDED_ADDITIONS.md by the same round-2 PR.

**Linked items.** ADR-0012, ADR-0007, ADR-0009, ADR-0010, ADR-0011, D-010, D-014, D-018, D-022, A-013, [`project/tasks/T-1.3.2.3-adr-0012-music-alignment.md`](../../project/tasks/T-1.3.2.3-adr-0012-music-alignment.md), [D-031](#d-031) (A-013 v1 → MVP).

---

### D-031 — A-013 section-to-media NL mapping reclassified from v1 → MVP (2026-05-02)

**Status:** accepted — scope reclassification (cross-cuts E-1.2 vision grooming and E-1.3 architecture grooming)

**Context.** A-013 (music-video output mode) originally had two phase tags: "MVP basic" (beat alignment of cuts to user-supplied music) plus "v1 add" (the section-to-media natural-language mapping where the user can describe which music sections should come from which media — "chorus = summit footage; bridge = rest stop"). During E-1.3 round-2 architecture grooming (Q10), the user redirected: pull the full version into MVP.

**Decision.** A-013 is **MVP in full**, including section-to-media natural-language mapping. The user's NL spec passes verbatim to the Tier-L Opus narrative judge (per ADR-0012 + ADR-0011 Stage 5); the judge handles the prose natively as one additional input alongside the brief + music structure. No structured-parse stage is required at MVP.

The v1 follow-on for A-013 narrows to: royalty-free music starter pack, licensed-library integration, and *conversational* section adjustments at chat-refine time ("make the bridge feel more contemplative"). The base section-to-media NL mapping is MVP.

**Alternatives considered.**
- *Keep section-to-media NL mapping at v1 (original A-013 plan).* The simpler MVP version — "music-video sub-mode with basic beat alignment only, no NL section mapping" — would have shipped first; full version arrives in v1. Rejected per Q10: pulling the full version into MVP is one prose field on the project; the Opus-tier judge handles it natively; no architectural debt. The user judged the differentiation worth the slight scope expansion.
- *Half-version at MVP (free-text "hint" passed to the judge but no first-class `section_mapping` output).* A middle ground from the round-2 proposal. Rejected — the structured `ArcJudgment.section_mapping` field is small and free; doing the half-version saves nothing and makes the v1 step ambiguous.
- *Reclassify in a follow-up post-E-1.3 cycle.* Rejected — the architectural surface is being pinned now in ADR-0012, so the scope reclassification belongs in this PR for self-consistency.

**Consequences.**
- `RECOMMENDED_ADDITIONS.md` A-013 entry's status reads "phase MVP (full version)" with a footnote noting the reclassification.
- `GROOMED_FEATURES.md` Story Video generation theme moves the section-to-media row from v1 to MVP.
- `MVP.md` adds the section-to-media NL spec to the locked must-do constraint set; the "Out of MVP scope" list drops the corresponding line.
- ADR-0012 carries the architectural realization (Stage 5 prompt assembly).
- The user's section-to-media spec is a single optional textarea at job creation. Empty spec = the judge proceeds without it (the original "music-video without NL mapping" flow).

**Linked items.** A-013 (entry updated), ADR-0012, ADR-0011, D-010, D-018, D-030 (the music-alignment ADR's record), [`docs/vision/GROOMED_FEATURES.md`](../vision/GROOMED_FEATURES.md), [`docs/roadmap/MVP.md`](../roadmap/MVP.md), [`project/tasks/T-1.3.2.3-adr-0012-music-alignment.md`](../../project/tasks/T-1.3.2.3-adr-0012-music-alignment.md).

---

### D-032 — Connector layer = Connector Python protocol; YouTube at MVP via OAuth + resumable upload; tokens in SQLite (Fernet-encrypted); default video privacy = public (2026-05-03)

**Status:** accepted (formalized in ADR-0013)

**Context.** D-007 fixes MVP platform = YouTube only; v1 adds Instagram/Facebook/X. A-003 makes the audit log MVP scope. ADR-0006 partially pinned the audit-log shape. Round-3 user redirects: Q1 default video privacy = public (user picks per upload, leaning on the explicit Approve gate D-020 as the safety net); Q2 token storage = all in SQLite (rejected the keyring proposal).

**Decision.** `Connector` Python protocol with `authenticate / is_authenticated / revoke_credentials / validate_artifact / upload`. `YouTubeConnector` MVP implementation uses `google-auth-oauthlib` + `google-api-python-client`; OAuth via local-loopback callback; YouTube Data API v3 `videos.insert` resumable upload, 256 MB chunks. Default video privacy on upload = `public` (user picks visibility explicitly per upload via the publish UI). Token storage in SQLite `connector_credentials` table with `access_token` + `refresh_token` Fernet-encrypted at rest (key at `~/.impact-crater/db/.fernet-key`, file-permissions 0600). Token refresh as a background task before every connector call.

Audit-entry shape (final): JSONL line + SQLite mirror per ADR-0006. Fields: `schema_version`, `timestamp`, `project_id`, `snapshot_id`, `platform`, `external_id`, `external_url`, `response_code`, `response_summary`, `render_content_hash`, `user_approval_token` (opaque, in-session-bound), `publish_metadata` (title + truncated-description + visibility + tags_count + scheduled_publish_at).

API rejection model: structured `ConnectorError` hierarchy (`ConnectorValidationError`, `ConnectorUploadError`, `ConnectorAuthError`) with `user_actionable` + `suggested_action`. YouTube error mapping table specified.

**Alternatives considered.**
- *Default video privacy = `private`.* Originally proposed; rejected per Q1.
- *OS keyring for token storage.* Originally proposed; rejected per Q2 — simpler dependency surface with SQLite + Fernet.
- *Plaintext tokens in SQLite.* Rejected — Fernet adds ~50 lines and meaningful protection.
- *Hosted OAuth callback URL.* Rejected — conflicts with self-hosted-first ethos.
- *Lazy auth on first publish.* Documented as fallback; setup-time auth is the pattern.
- *Skip audit log at MVP.* Rejected — A-003 puts it in MVP scope.

**Consequences.** UI must make visibility selector unmissable; Approve button shows the selected visibility one more time before clicking. Token-refresh adds one SQLite read per connector call; negligible. Fernet key must be backed up for credential portability across machines. YouTube Data API quota caps practical usage at ~6 publishes/day per account; surfaced via ADR-0015. `Connector` protocol is the v1 contract (adding platforms = N new files). `user_approval_token` distinguishes user-initiated publishes from system-initiated retries; in-session-bound, opaque. Per-platform formatting lives in ADR-0010/0011, not here.

**Linked items.** ADR-0013, ADR-0005, ADR-0006, ADR-0007, ADR-0010, ADR-0011, ADR-0014, ADR-0015, D-007, D-020, A-003, A-008, A-009, [`project/tasks/T-1.3.3.1-adr-0013-connector-layer.md`](../../project/tasks/T-1.3.3.1-adr-0013-connector-layer.md).

---

### D-033 — Agent harness = single orchestrator with consolidated tool surface; cross-project user profile + agentic learning loop (2026-05-03)

**Status:** accepted (formalized in ADR-0014)

**Context.** D-017 fixed MVP harness as single orchestrator with structured tool calls. Round-3 grooming consolidated the tool surface from rounds 1-3 and locked the reasoning model + failure-mode UX. Per Q4 user redirect ("we can learn from the chat memories across projects, and build a user profile over time which can help the impact crater suggest ideas to the user itself during new project creations, or also help impact crater to learn from its mistakes the next time around"), the original "no chat-memory beyond current loop" proposal expanded to a cross-project user profile + agentic learning loop — filed as N-010.

**Decision.** Single `Orchestrator` class on Tier-M Sonnet 4.7 (per ADR-0009). Tool registry with per-tool `idempotency_class` (free / project_mutating / external_side_effect); external_side_effect tools require explicit user confirmation per call. Consolidated tool surface enumerates LLM operations + pipeline + refinement + music + connector + person-library + new profile tools. Reasoning model = tool-call loop bounded at 50 turns per session (refinement subloop has its own 10-turn bound per ADR-0011). Failure-mode UX (Q3) = three actions (continue / abandon / restart); manual override = v1.

**Cross-project user profile (N-010 architectural realization):** persisted at `~/.impact-crater/profile/profile.json` + `~/.impact-crater/profile/feedback_log.jsonl`. Profile schema = `StylePreferences` + `OrchestratorPriors` + `NarrativePatterns` + feedback-log pointer. Feedback log = append-only JSONL with event types (approve, refine, second_guess_accepted/rejected/modified, refinement_succeeded/failed, pre_filter_overridden, effort_level_overridden, publish_succeeded/failed, job_cancelled). Profile derived from feedback log via `derive_profile_priors` Tier-M call; re-derivation on job-end + after every N=10 events incrementally + every N=100 full. Profile read at: job creation (suggestions + pre-filled form), brief parsing (in-context priors), Stage 4 quality floor override, Stage 5 narrative-arc judgment (in-context patterns), Stage 6 second-guess threshold, Stage 9 refinement strategy bias.

**Privacy posture for the profile:** all on disk; never leaves machine except as in-context priors in Tier-M LLM calls; person-library data does NOT flow into profile (profile sees abstracted patterns, not identities); user can reset profile + feedback log via settings.

**Cancellation + resume:** `JobCancelled` propagates through tool-call loop and worker pool; on startup, FastAPI scans for `in_progress` snapshots and surfaces "Resume?" prompts.

**Alternatives considered.**
- *No chat-memory beyond current loop (original proposal).* Stateless per-project. Rejected per Q4.
- *Multi-agent harness at MVP.* Rejected per D-017; v2.
- *Model fine-tuning per user.* Rejected — expensive infra; profile-based in-context priors are immediate and cheap.
- *Per-project-only learning.* Rejected per Q4 — cross-project value is the differentiator.
- *Manual override at MVP.* Rejected per Q3; v1 power-user feature.
- *Profile derivation via deterministic rules (no LLM).* Rejected — motif extraction + narrative-pattern detection benefit from LLM understanding.
- *Profile in SQLite.* Rejected — JSON file simpler for <50 KB document; feedback log uses JSONL for append-only simplicity.

**Consequences.** Orchestrator is no longer stateless across projects (the differentiator). Profile re-derivation = ~$0.005/job (negligible). Feedback log grows over time; rotation policy in ADR-0015. One-click profile reset. Profile schema v1 is the contract for v1 profile-driven UX. 50-turn bound is conservative; raise if MVP testing shows productive jobs hitting it. Multi-tenant (v3) requires per-tenant profile path. external_side_effect class ensures publish-style calls always require user confirmation.

**Linked items.** ADR-0014, ADR-0005, ADR-0006, ADR-0007, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013, ADR-0015, ADR-0016, D-017, D-013, D-022, A-005, A-015, **N-009** (refinement strategy now reads profile priors), **N-010** (novel mechanism filed in NOVEL_IDEAS.md), [`project/tasks/T-1.3.3.2-adr-0014-agent-harness.md`](../../project/tasks/T-1.3.3.2-adr-0014-agent-harness.md).

---

### D-034 — Resource accounting = telemetry JSONL + JobCostSummary + dual-cap quota (total + per-provider); first-time-setup spend cap, no system default (2026-05-03)

**Status:** accepted (formalized in ADR-0015)

**Context.** D-013 (effort levels) + A-004 (per-day spend cap) + A-015 (cost-transparency UI) + N-006 (effort-level UX) all need a concrete telemetry + quota substrate. Round-3 user redirects: Q5 daily spend cap = user-set during first-time setup, no system default; Q6 spend cap shape = both total + per-provider caps.

**Decision.** Telemetry stream = append-only JSONL at `~/.impact-crater/telemetry.jsonl` (separate from audit + feedback logs). Event types: `LLMCallEvent` (per ADR-0007), `RenderEvent`, `IngestEvent`, `OrchestratorTurnEvent`, `JobLifecycleEvent`. Each event has `correlation_id` ties multiple events from one orchestrator turn together.

`JobCostSummary` persisted at `snapshots/{snapshot_id}/cost_summary.json` at job-end. Schema includes per-tier counts/cost, per-provider cost, per-operation cost, cache stats with `estimated_cost_saved_by_cache_usd`, render stats, total. Source-of-truth for post-job UI + orchestrator profile-prior re-derivation (per ADR-0014).

Rate cards = YAML files at `config/rate-cards/{provider}-{model}-{version}.yaml`; versioned per ADR-0007 `model_version`; shipped with wheel; user manually updates on rate change.

**Dual-cap quota model (Q6):** SQLite `quota_state` table partitioned by date + provider; `_total_` row aggregates. A job is allowed only if BOTH total cap AND per-provider caps would not be exceeded. Mid-job pause-and-prompt if caps approached. Pre-job + per-stage check.

**First-time-setup spend cap (Q5):** mandatory step in setup wizard; no system default; user enters total cap (≥$1) + optional per-provider caps; editable later in Settings.

**UI surfaces:** pre-job cost preview with per-tier breakdown + remaining budget for both caps; in-job live spend; post-job JobCostSummary; settings panel with editable caps + monthly history.

**Telemetry retention:** kept forever at MVP; manual cleanup via Settings; rotation deferred to v1. Same policy applies to feedback log (per ADR-0014).

**Costs not covered at MVP:** local-LLM compute (v1; switches to seconds-of-compute), disk usage (manual cleanup), network bandwidth (not tracked).

**Alternatives considered.**
- *System default for spend cap (e.g., $50/day).* Originally proposed; rejected per Q5.
- *Single total-cap only.* Originally proposed; rejected per Q6.
- *Per-provider-only (no total).* Considered; rejected — total is simpler conceptual surface.
- *Telemetry to a remote service.* Rejected — self-hosted-first ethos.
- *Auto-archive telemetry > 90 days.* Rejected at MVP — manual is fine.
- *Quota check at every LLM call.* Rejected — pre-job + per-stage is sufficient and lower latency.
- *Soft cap (warn but allow).* The pause-and-prompt is the soft escape hatch; the cap is hard otherwise.
- *Continuous effort slider.* Rejected per D-013 — pre-canned levels with agentic recommendation.

**Consequences.** First-time-setup wizard becomes mandatory. Mid-job pause-and-prompt for cap-approach. JobCostSummary is load-bearing for ADR-0014 profile re-derivation. Cache hits show $0 cost but contribute to estimated_cost_saved rollup. Rate-card files versioned + maintained per release. Telemetry-rotation policy deferred to v1; schema is rotation-friendly. Local-LLM cost model is a v1 ADR follow-on.

**Linked items.** ADR-0015, ADR-0005, ADR-0006, ADR-0007, ADR-0009, ADR-0011, ADR-0013, ADR-0014, ADR-0016, D-013, A-004, A-015, N-006, [`project/tasks/T-1.3.3.3-adr-0015-resource-accounting.md`](../../project/tasks/T-1.3.3.3-adr-0015-resource-accounting.md).

---

### D-035 — Privacy posture defaults: three project-level toggles + privacy-sensitive routing extension to ADR-0007 (2026-05-03)

**Status:** accepted (formalized in ADR-0016)

**Context.** A-002 made privacy posture MVP because D-016 puts images off-device. Round-3 user redirects: Q7 blur-faces default OFF + the novel "blur ON triggers face-ops routed to local LLM only when local available" mechanism (N-011); Q8 strip-GPS-only as separate toggle from full-EXIF-strip.

**Decision.** Three project-level toggles in `manifest.json`: **Strip EXIF default ON** (removes camera/device info, software, lens, ISO; implies GPS-strip ON); **Strip GPS only default ON** (subset; preserves timestamps; only takes independent effect if full-EXIF-strip is OFF); **Blur faces default OFF** (when ON, face-related features skipped on remote calls; UI surfaces trade-off; **if local-LLM available per ADR-0008, face ops route to local per N-011**).

**EXIF/GPS strip implementation:** source media never modified in place; stripped variants cached at `~/.impact-crater/projects/{id}/cache/stripped/{content_hash}.{ext}` keyed by strip mode; deterministic, reusable across projects.

**Face-blur implementation:** lightweight CPU face-detection library (dlib `face-recognition` or mediapipe — confirmed at first feature work) for blur masking ONLY (the one use case where vision-LLM-only doesn't fit because we need detection BEFORE sending to LLM). Gaussian blur on detected face boxes. Cached at `~/.impact-crater/projects/{id}/cache/face_blurred/{content_hash}.{ext}`.

**Privacy-sensitive routing extension to ADR-0007 (N-011 architectural realization):** per-operation `privacy_class` (face_data / visual_only / derived_metadata / text_only) + per-provider `eligibility_for_class` declared in `config/llm-routing.yaml` and `config/providers.yaml`. When blur-faces ON, remote providers' eligibility for `face_data` is dynamically removed; if local provider exists + eligible, route there with unblurred image; otherwise skip operation with degraded-metadata fallback (Stage 5 prompt variants handle missing person data; Privacy Banner surfaces the consequence).

**Plug-and-play hook (MVP):** all routing infra in place at MVP — when v1 ships ADR-0008 local-LLM runtime, no code changes needed for privacy-routing feature.

**Person-library + face-blur interaction:** library lives in SQLite locally; never sent except as labeled reference collage. With blur-faces ON + remote-only, collage not built. With blur-faces ON + local routing, collage sent to local only.

**Audit log + profile privacy:** audit log unaffected (publish events, not analysis). Profile sees abstracted patterns, not identities. Profile read into Tier-M calls; provider "API data not used for training" guarantees apply.

**Settings UI:** per-project defaults + plain-English explainer + person-library link + reset-profile button. Per-image privacy review mode = v1 ("high-privacy mode").

**Alternatives considered.**
- *Blur-faces default ON.* Rejected per Q7 — silently disabling person-library is hostile UX.
- *Single EXIF-strip toggle.* Rejected per Q8 — timestamps wanted.
- *No privacy-sensitive routing.* Rejected per Q7 — user wants the local-LLM hook baked in.
- *Pre-emptive face-blur for any LLM call.* Defeats N-011's local-route. Rejected.
- *Skip the deterministic face-detection lib.* Can't — blur path needs detection BEFORE sending. Accepted as the one face-detection-only dep.
- *More granular privacy classes.* Rejected at MVP; four is enough.
- *Per-image review mode.* Friction-heavy; deferred to v1.

**Consequences.** Privacy panel = real UI surface design needed at MVP. One new face-detection-only dep (dlib or mediapipe) for blur masking. ADR-0007 routing config schema gets `privacy_class` + `eligibility_for_class` fields. Skipped-operation degradation needs Stage-5 prompt variants that handle missing person data. The plug-and-play hook means v1 local-LLM is "drop runtime in" — no architectural changes. The "API data not used for training" assumption is documented as third-party promise. Cache invalidation on privacy-toggle change: flipping blur-faces ON invalidates `face_data`-class cached operations.

**Linked items.** ADR-0016, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0013, ADR-0014, A-002, D-016, **N-002** (operation-aware router future — sibling to N-011), **N-008** (person library), **N-010** (cross-project profile), **N-011** (novel mechanism filed in NOVEL_IDEAS.md), [`project/tasks/T-1.3.3.4-adr-0016-privacy-posture.md`](../../project/tasks/T-1.3.3.4-adr-0016-privacy-posture.md).

---

### D-036 — MVP execution roadmap = 9 milestones M0..M9 (E-2.1..E-2.9 under I-2 MVP); AI-assisted full-time velocity (4-8 weeks calendar) (2026-05-03)

**Status:** accepted

**Context.** E-1.3 closed 2026-05-03 with all 12 architecture ADRs accepted (ADR-0005..0016). The architecture is fully scoped. The next step is execution planning: which work happens when, in what sequence, with what shipping criterion per milestone. This is the E-1.4 work.

**Decision.** Partition MVP into **9 milestones** M0..M9, each mapped 1:1 onto an Epic under a new `I-2 MVP` initiative (E-2.1..E-2.9). Per-milestone shipping criteria documented in `MVP.md`. Effort estimates use the project's standard scale (S<4h, M<1d, L<3d, XL>3d) interpreted as **focused-build session-time**, not calendar time.

**Velocity assumption.** AI-assisted full-time aggressive: the user is PM/EM/Architect; Claude does the build via Anthropic's Max 20x plan. Total session-time estimate ~22-30 days of focused build ≈ **4-8 weeks calendar time** (the lower bound assumes minimal real-world iteration in M9; upper bound assumes meaningful real-world fixes after the first end-to-end run).

**Milestone partition:**

| # | Milestone | Epic | Effort |
|---|---|---|---|
| M0 | Scaffolding | E-2.1 | L |
| M1 | Headless curation through Stage 5 | E-2.2 | XL |
| M2 | Render + standard mode | E-2.3 | L |
| M3 | UI MVP loop closed | E-2.4 | XL |
| M4 | Music-video mode + section-to-media NL | E-2.5 | L |
| M5 | Person library + privacy panel | E-2.6 | XL |
| M6 | Agentic refinement + orchestrator second-guess | E-2.7 | XL |
| M7 | YouTube publish | E-2.8 | L |
| M8 + M9 | Cross-project profile + polish + D-014 validation | E-2.9 | L (build) + open-ended (validation) |

**Critical-path risks** (5 flagged, with mitigations in MVP.md): LLM provider drift; render perf at MVP scale; person-library UI complexity; cross-project profile derivation quality; Claude session bandwidth.

**Pre-flight criteria for declaring MVP done** (10 checkboxes in MVP.md): headlined by D-014 success-criterion verified end-to-end on a real user dataset.

**Alternatives considered.**
- *Single-human-dev velocity (~26 weeks).* The historical baseline. Rejected — user-set velocity is AI-assisted full-time per round-1 redirect Q3.
- *Fewer milestones (e.g., 5).* Coarser milestones lose the demoable shipping-criterion granularity. Rejected — 9 milestones each have a clean demo.
- *More milestones (e.g., 15+).* Over-fragmentation; per-milestone setup overhead grows. Rejected.
- *Roll M8 (cross-project profile) into a v1 launch instead of MVP.* Considered. Rejected per D-037 — keep all E-1.3 MVP scope expansions.
- *Deterministic-only profile derivation deferred to v1; MVP ships without N-010 entirely.* Considered. Rejected — N-010 is the differentiator and the deterministic version is small.

**Consequences.** I-2 MVP initiative + 9 epic shells filed in this PR. Per-epic story / task decomposition happens when each epic opens for work. The PR auto-merges per ADR-0004; M0 (E-2.1 Scaffolding) becomes the first ready epic when E-1.4 closes (round 2 ROADMAP.md still pending). After E-1.4 closes, **the next thing is the first commit of code**.

**Linked items.** D-014 (the validation target), [`docs/roadmap/MVP.md`](../roadmap/MVP.md), [`project/initiatives/I-2-mvp.md`](../../project/initiatives/I-2-mvp.md), [`project/epics/E-2.1-scaffolding.md`](../../project/epics/E-2.1-scaffolding.md) through [`E-2.9`](../../project/epics/E-2.9-cross-project-profile-mvp.md), [`project/tasks/T-1.4.1.1-mvp-md-final-lock.md`](../../project/tasks/T-1.4.1.1-mvp-md-final-lock.md), [`T-1.4.1.2`](../../project/tasks/T-1.4.1.2-create-i2-mvp-initiative-and-epics.md).

---

### D-037 — Keep all E-1.3 MVP scope expansions in MVP — no scope cut for time (2026-05-03)

**Status:** accepted

**Context.** E-1.3 expanded the MVP scope meaningfully:

- **N-008** person-library + reference-collage face recognition (round 2)
- **N-009** agentic refinement with custom plan generation (round 2)
- **N-010** cross-project user profile + agentic learning loop (round 3, MVP minimum-viable shape)
- **N-011** privacy-sensitive operation routing (round 3, architectural hook only at MVP)
- **A-013** section-to-media NL mapping reclassified v1 → MVP via D-031 (round 2)

E-1.4 round 1 needs to ratify or trim this expanded scope before sequencing. Cutting any item saves ~3-4 weeks of focused build per item.

**Decision.** **Keep all of N-008 + N-009 + N-010 + N-011 + A-013 in MVP.** No scope cut for time. The differentiation is in the novel mechanisms; cutting them produces a generic v0 that doesn't differentiate from existing AI-driven media-curation tools.

**Specific MVP-shape clarifications:**
- N-008 ships in full MVP form (per-person 5 face photos default; reference-collage construction; recognition with confidence scores; cache-correct integration).
- N-009 ships in full MVP form (5-strategy thinking step; bounded 10-turn loop; cost-aware bias; per-snapshot persistence).
- N-010 ships **minimum-viable**: feedback log capture + deterministic frequency-based profile derivation. The LLM-driven re-derivation per ADR-0014 is **deferred to post-launch**, when there's enough feedback log data to validate it adds value over the deterministic version.
- N-011 ships **architectural hook only**: routing-config schema with per-operation `privacy_class` + per-provider `eligibility_for_class` + graceful-degradation path. The actual local-LLM destination is v1 work per ADR-0008; MVP just lands the routing infra so v1 ships the feature with zero code changes.
- A-013 ships in full MVP form (free-text NL spec passed verbatim to Stage 5; the Tier-L Opus judge handles prose natively).

**Alternatives considered.**
- *Cut N-008 (person library) to ship faster.* Saves ~3 weeks. Rejected — narrative judgment without per-person identity is meaningfully weaker; "make a video about my family vacation" loses its primary signal.
- *Cut N-009 (agentic refinement) to ship faster.* Saves ~3 weeks (refinement becomes simple Stage-5-rerun). Rejected — refinement UX is product-defining; the agentic version is genuinely better.
- *Cut N-010 (cross-project profile) to ship faster.* Saves ~2 weeks (no profile substrate at all). Rejected — the cross-project learning is the long-term differentiator; even the deterministic minimum-viable version starts capturing data immediately for v1's LLM-driven derivation.
- *Cut N-011 (privacy-routing) to ship faster.* Saves <1 week (the routing infra is small). Rejected — N-011 is mostly "schema fields + graceful-degradation path," tiny relative to the privacy story.
- *Cut A-013 (section-to-media NL) to ship faster.* Saves nothing (it's one prose field passed to Stage 5). Already-pulled into MVP per D-031.

**Consequences.** MVP timeline 4-8 weeks under AI-assisted velocity per D-036. The differentiated v0 is the product the user is willing to publish to their own YouTube channel — that's the test. v1 builds on the substrate this MVP creates (local-LLM, multi-platform, live-job, reference-media style, full N-010 LLM-driven re-derivation).

**Linked items.** D-036 (the milestone partition), N-008, N-009, N-010, N-011, A-013, D-031 (A-013 reclassification), ADR-0008 (local-LLM v1 work that completes N-011), ADR-0014 (full N-010 LLM-driven re-derivation deferred to post-launch).

---

### D-038 — Code-organization sequencing: vertical-slice-early + backend-before-frontend-per-milestone + inline-tests (2026-05-03)

**Status:** accepted

**Context.** With the 9-milestone partition locked (D-036) and the full MVP scope kept (D-037), how should the actual code work be organized within and across milestones?

**Decision.** Three sequencing principles:

1. **Vertical-slice-early.** M1 (headless curation through Stage 5) is end-to-end through the LLM stack + pipeline + telemetry + worker pool **before any UI investment**. This validates the entire stack works (provider auth, routing, telemetry, worker pool, cache, structured-output schemas) on a small test set before committing to UI build-out. If a Stage 5 fails to produce a coherent ArcJudgment from a test set, the issue is found and fixed before UI work compounds the rework cost.

2. **Backend-before-frontend per milestone.** Within each milestone (M3 onward, where UI work is part of the deliverable), API endpoints + tool implementations land first; React components consume the shaped APIs second. The orchestrator's tool surface drives the API shape; the UI is a thin layer over the shaped APIs. Avoids the anti-pattern where UI design constrains the API shape into something awkward.

3. **Inline tests, not after.** `pytest` + `pytest-asyncio` + `pytest-mock` for backend; `vitest` + `@testing-library/react` for frontend. Tests land alongside the code they cover, not in a "tests later" sweep. Coverage growth tracks feature growth.

**Alternatives considered.**
- *UI-first / design-driven.* Build the UI first to validate the user experience, then back-fill the implementation. Rejected — for an MVP where the LLM stack is the riskiest piece, validating it first is more important than validating UX (which can be iterated post-launch).
- *Horizontal-slice (build all backend, then all frontend, then integrate).* Rejected — too much integration risk at the end; vertical slices catch integration issues per milestone.
- *Tests later.* Rejected — bad practice; the project's coding standards (CLAUDE.md) already imply "tests with code."
- *No tests until M9 polish.* Rejected — same as above.

**Consequences.** M1 + M2 produce a headless usable system before M3 starts UI build. Each later milestone (M3, M4, M5, M6, M7, M8) follows backend-then-frontend within itself. Test infrastructure lands in M0 (`pytest` + `vitest` configs); per-feature test coverage grows from M1 onward.

**Linked items.** D-036 (the milestone partition this sequences within), [`docs/roadmap/MVP.md`](../roadmap/MVP.md) §"Milestones" (the canonical milestone list), [`project/epics/E-2.1-scaffolding.md`](../../project/epics/E-2.1-scaffolding.md) (M0 sets up the test infra).

---

### D-039 — v1 / v2 / v3 phase sequencing locked in ROADMAP.md (2026-05-03)

**Status:** accepted (closes E-1.4; closes I-1; exits the scaffolding phase)

**Context.** With MVP scope locked (E-1.4 round 1) and the architecture fully scoped (E-1.3, 12 ADRs), the last scaffolding-phase work is locking the post-MVP roadmap. ROADMAP.md was a stub with the 5-phase shape (`scaffolding`/`mvp`/`v1`/`v2`/`v3`) but no per-phase milestone bullets. E-1.4 round 2 fills it in with concrete v1 / v2 / v3 sequencing.

**Decision.** Lock the v1 / v2 / v3 milestone sequencing as the authoritative post-MVP roadmap.

**v1 — 9 milestones (~6 months at AI-assisted velocity):**

| # | Milestone | Why this slot |
|---|---|---|
| v1.1 | Local-first LLM (Ollama + N-002 router; N-011 becomes functional) | Most-promised v1 feature (D-016 + N-002 + N-011 all depend on it); biggest brand differentiator after MVP; somewhat self-contained |
| v1.2 | Live job (A-012 + N-005) | The user's most novel post-MVP claim; ships early so the differentiation lands before incremental polish |
| v1.3 | Multi-platform: Instagram + Facebook + X bundled (with A-008 watermark) | Same architecture per-connector; bundling reduces per-milestone overhead; Instagram first because it's the most popular short-video platform after YouTube |
| v1.4 | Reference-media style learning (A-014 + N-004) | Independent feature; needs a dedicated milestone for the style-fingerprint mechanism |
| v1.5 | Power-user + polish bundle | Multi-version comparison + quality floor + L4-L5 + full cost-transparency UI + upgrade-path agent + manual-override + per-image privacy + project export — all "table-stakes polish" that benefits from being grouped |
| v1.6 | Auto photo / video editing | More table-stakes than differentiator; comes after the differentiation milestones |
| v1.7 | Music sourcing expansion (royalty-free + licensed library + A-013 conversational sections) | Independent; can ship anytime in v1 |
| v1.8 | LLM-driven profile re-derivation (full N-010) | Needs the deterministic version (MVP) shipped first to gather feedback log data; then upgrades the derivation |
| v1.9 | Cross-job cache full (A-011 → N-007) | Engineering polish; replaces MVP-lite cache with the full N-007 schema |

**v2 — 4 milestones (~3-4 months):**

| # | Milestone | Why this slot |
|---|---|---|
| v2.1 | Full mobile UI | Builds on v1.2's camera-roll watcher; the natural mobile-first capability |
| v2.2 | Multi-agent harness (per D-017 v2 commitment) | Required substrate for v2.3 conversational-at-scale |
| v2.3 | Conversational refinement at scale | Powered by v2.2 multi-agent |
| v2.4 | Generated music (Suno-class) | Quality + cost bounds need to be reasonable when committed; deferred to v2 to avoid committing to an external vendor's quality trajectory in v1 |

**v3 — 3 milestones (timing TBD; depends on go-to-market):**

| # | Milestone | Why this slot |
|---|---|---|
| v3.1 | Hosted infra (object-storage + Postgres swap per ADR-0006) | Engineering substrate; the swap is a config flip per ADR-0006 design |
| v3.2 | Multi-tenant (auth + billing + per-tenant isolation) | Requires v3.1 |
| v3.3 | Public launch (landing page + onboarding + support + BSL Change Date 2030-04-25 review) | Final go-to-market |

**Total path from MVP-start to v3 launch:** ~12-18 months calendar at AI-assisted velocity.

**Alternatives considered.**
- *v1.2 live-job placement = v1.3 or v1.4 (after multi-platform).* Multi-platform reach matters too. Rejected — live-job is the most novel claim; ship the differentiation early.
- *v1.3 multi-platform split into v1.3a / v1.3b / v1.3c (one platform per milestone).* Rejected — the architecture is the same per-connector; bundling reduces per-milestone overhead.
- *v1.6 auto-editing earlier (e.g., v1.2).* User-perceived quality jump matters. Rejected — differentiators ship first; auto-editing is more table-stakes.
- *Generated music (v2.4) earlier (v1.7 / v1.8).* Suno's quality keeps improving. Rejected — don't commit to an external vendor's quality trajectory in v1; revisit when v1 closes.
- *v3 calendar ETA.* Rejected — depends on go-to-market readiness, not engineering readiness; left intentionally TBD.
- *Per-milestone story / task decomposition at this scope decision.* Rejected — premature; per-epic decomposition happens when each epic opens for work (the same pattern E-2.1..E-2.9 follow).
- *Create I-3 v1 / I-4 v2 / I-5 v3 initiative shells now.* Rejected — these initiatives are months away; the ROADMAP.md milestone bullets are sufficient until v1 actually opens. When v1 opens (post-MVP), the same E-1.4-style roadmap-grooming epic will create I-3 + v1 epic shells.

**Consequences.**
- ROADMAP.md is placeholder-free with the 5-phase × per-phase-milestones shape.
- v1 milestone count (9) and ordering are locked under D-039; later D-NNNs can supersede if MVP findings justify re-sequencing.
- v1 scope explicitly drops: anything that survived to MVP via D-037 stays in MVP; anything in `RECOMMENDED_ADDITIONS.md` tagged v1 is now scheduled to a specific v1 slot.
- Timing assumptions (4-8 weeks MVP, 6 months v1, 3-4 months v2, TBD v3) are anchors, not commitments. Phases ship when they ship.
- **Closing this decision closes E-1.4. Closing E-1.4 closes I-1 (all 5 child epics done). Closing I-1 exits the scaffolding phase.** I-2 promotes from `backlog` to `in-progress`. E-2.1 (Scaffolding M0) becomes the first ready epic = first commit of code in the next session.

**Linked items.** D-036 (MVP execution roadmap; v1/v2/v3 sequence here builds on the MVP-shape there), D-014 (the success criterion that gates MVP→v1 transition), all `phase: v1` / `v2` / `v3` items in `RECOMMENDED_ADDITIONS.md` and `GROOMED_FEATURES.md` are now slotted into a specific v1.x / v2.x / v3.x milestone, [`docs/roadmap/ROADMAP.md`](../roadmap/ROADMAP.md), [`project/tasks/T-1.4.2.1-roadmap-md-final-lock.md`](../../project/tasks/T-1.4.2.1-roadmap-md-final-lock.md), [`project/tasks/T-1.4.2.2-d-039-and-cascading-closure.md`](../../project/tasks/T-1.4.2.2-d-039-and-cascading-closure.md).

















---

### D-040 — LLM cache payload filenames must embed the cache key

- **Status:** accepted
- **Date:** 2026-06-11
- **Context:** The 2026-06-11 manual test job failed with `stage4_empty_candidate_set` (all 36 assets below the 0.40 quality floor). Root cause: `cache_key()` includes `params_canonical` (score dimension + brief hash) but the on-disk payload path did not, so the quality score and every brief''s narrative-relevance score for one photo shared a single file — each write overwrote it while all `cache_index` rows kept pointing at it. A "quality" cache hit could return a stale narrative score from an earlier brief; one photo had 8 index rows → 1 file. First symptom had appeared 2026-05-07 and was misattributed to a vague brief.
- **Decision:** Payload filename embeds `cache_key[:12]` (`{operation}_{prompt_version[:16]}_{cache_key[:12]}.{json|npy}`), making the file unique per index row. Poisoned `score_image` rows purged via SQL migration `002_purge_score_image_cache.sql` (`DELETE FROM cache_index WHERE operation=''score_image''`); orphaned payload files left on disk (harmless). Cache-class invalidation by migration is now the established pattern. Stage4EmptyCandidateSet additionally reports the observed quality-score range and labels the all-zeros case an app bug rather than blaming the user''s brief.
- **Alternatives considered:** Purge only provably-colliding rows (rejected: every score_image row was untrustworthy — cannot tell which dimension''s value a file holds); bump the score prompt template to rotate prompt_version (rejected: obscures intent, leaves the latent path bug in place).
- **Consequences:** Re-scoring a 36-asset job after the purge costs ~$0.04 (Tier-S Flash). Every cached operation is now collision-safe per params variant. Fixed in PR #35.
- **Linked ADRs / items:** ADR-0006 (cache_index), ADR-0007 (LLM abstraction), A-011 / N-007 (content-addressed analysis cache).

---

### D-041 — Music-video beat-snap: clip boundaries snap to the grid; never truncate the timeline

- **Status:** accepted
- **Date:** 2026-06-11
- **Context:** ADR-0012 says clip durations come "from the snapped grid". The M4 implementation read that as one clip per beat-grid interval, dropping any timeline beyond the last selected clip: a 13-clip / 60s-target Zion job rendered 25.3 seconds and the song stopped mid-crescendo. Stage 5 had already paced the 13 clips to cover the 60s arc; Stage 6 discarded that pacing.
- **Decision:** Stage 6 music-video mode now (1) linear-scales the Stage-5 clip durations so the timeline sum ≈ target duration, then (2) snaps each clip *boundary* to the nearest beat-grid cut point (monotonic, ≥250ms per clip), forcing the final boundary to the target. Cuts land on beats; the video covers the full target; video-scene clips stay capped by their natural length. Two companion render fixes ride the same decision: Stage 7 trims + fades audio against the actual summed timeline (not `target_duration_ms` — the mux is `-shortest`, so a fade computed past the video end never played), and Stage 1 ingest + the Anthropic re-encode path apply `ImageOps.exif_transpose` so portrait phone photos carry display dimensions through aspect decisions and reach vision LLMs upright.
- **Alternatives considered:** One clip per grid interval, silent tail (status quo — rejected: violates the user''s target duration and discards Stage-5 pacing); filling the tail by looping clips (rejected: "the user picked a target duration" cuts both ways — invent no content the judge didn''t order).
- **Consequences:** Music-video renders run the requested duration with beat-aligned transitions (retest: 60.0s exactly, 11/12 interior boundaries on cuts, the off-grid one a natural-length-capped video scene). Audible fade-out in both modes (−19→−39 dB measured). No more sideways/pillarboxed portrait photos. Fixed in PR #36.
- **Linked ADRs / items:** ADR-0011 (Stage 6 plan compile), ADR-0012 (music alignment), D-040 (same test session).

---

### D-042 — Trip Package is the north-star feature, gated on single-video quality mastery

- **Status:** accepted
- **Date:** 2026-06-11
- **Context:** In the 2026-06-11 grooming session the user articulated the product''s ultimate feature (A-020 / N-013): dump a whole multi-day trip''s media, walk away, and receive a complete package — per-location/event videos, reels of special moments, an overall trip video, and a montage. In the same breath the user set the sequencing constraint: "unless the individual videos created are acceptable quality, the ultimate package feature obviously doesn''t make sense, because it is built on top of this individual video creation capability."
- **Decision:** (1) The Trip Package (A-020/N-013) is groomed and slotted at **v2**, with its deterministic seeds in v1.2''s multi-output orchestration. (2) Single-video quality mastery is the explicit gate: v1 quality work — A-016 cheap-first analysis hardening, A-017 semantic near-duplicate suppression, quality-floor calibration (A-007), style learning (v1.4), auto-editing (v1.6) — ships first and is judged against the user''s taste on real media. (3) Supporting casts: A-018 auto trip cast (v1-late/v2, design N-012) feeds both curation quality and the package planner; A-019 crowd removal parks at v2+. (4) No package-feature code lands before the gate is met; the MVP gate discipline (CLAUDE.md) applies unchanged.
- **Alternatives considered:** Build a thin package pilot now on top of the current pipeline (rejected: multiplies an unproven quality bar across N artifacts and burns Tier-L spend per artifact); slot the package at v1 (rejected: v1 is already a committed 9-milestone sequence per D-039, and the planner belongs naturally with the v2.2 multi-agent harness).
- **Consequences:** RECOMMENDED_ADDITIONS gains A-016..A-020; NOVEL_IDEAS gains N-012/N-013; GROOMED_FEATURES gains a new theme 14 (Trip Package) and curation-engine rows; S-2.9.5 + S-2.9.6 filed as the first two v1 quality stories. ROADMAP v1/v2 milestone tables remain unchanged per D-039 — A-016/A-017 fold into existing v1.5/v1.6-class polish slots; A-020 anchors v2 scope when v2 opens.
- **Linked ADRs / items:** A-016, A-017, A-018, A-019, A-020, N-012, N-013, D-039, S-2.9.5, S-2.9.6.

---

### D-043 — Preparation-phase overhaul: extract chronology + rich metadata + cheap-first + best-of-burst before planning

- **Status:** accepted
- **Date:** 2026-06-11
- **Context:** A 4-agent audit of the preparation+planning phases (2026-06-11) found the app extracted no capture timeline (EXIF/filename/mtime all ignored; GPS only stripped, never read), a metadata schema missing 9 of the user's 15 desired signals, full-size 9-12 MB originals shipped to every LLM call, and a per-asset image embedding computed every job and then discarded. The user asked the app to "extract as much information from the media before planning as possible" and explicitly named the prerequisites for the Trip Package: cheap-first analysis, retake suppression, main-people identification, crowd removal.
- **Decision:** Land the preparation-phase foundation as MVP-hardening before the heavier v1/v2 features: (1) A-021 chronology extraction + GPS read, timeline fed to the planner (judge defaults to forward-in-time); (2) A-022 metadata enrichment (shot type, per-person expression, main-vs-other people, scenery, camera-quality text, specialness, safety, obstructions) + a Stage-4 safety floor; (3) A-016 cheap-first analysis (1024px renditions to the VLM, long video scenes subdivided); (4) A-017 best-of-burst semantic dedup activating the previously-dead embeddings, time-windowed by the new chronology. Main-people identification (A-018) and crowd removal (A-019) carry dependency/privacy decisions and are sequenced AFTER this foundation, behind explicit user decisions, still under the D-042 single-video-quality gate.
- **Alternatives considered:** Jump straight to A-018/A-019 (rejected: both assume chronology + face infra this foundation provides, and A-017's time-windows would have nothing to window on); leave analysis on full-size originals (rejected: ~10x bandwidth for no VLM-quality gain); keep embeddings unused (rejected: they were already paid for and are exactly what semantic dedup needs).
- **Consequences:** New `media/timeline.py`; migration 003 (capture_timestamp/source/confidence + gps_lat/lon on media); RichMetadataPhoto + extraction prompt + judge prompt expanded; Stage 2/3 analyze renditions; Stage 4 gains safety floor + semantic best-of-burst with a dedup-aggressiveness knob; Stage2AssetOutputs carries the embedding in-memory. RECOMMENDED_ADDITIONS gains A-021/A-022; NOVEL_IDEAS gains N-014; S-2.9.5/S-2.9.6 advanced. A-018/A-019 await user decisions (face-embedding dependency; generative-inpaint backend + privacy).
- **Linked ADRs / items:** A-016, A-017, A-021, A-022, N-014, D-042, S-2.9.5, S-2.9.6, ADR-0011.

---

### D-044 — Configurable backends for face-ID (A-018) and crowd removal (A-019): cloud default + optional local upgrade

- **Status:** accepted
- **Date:** 2026-06-11
- **Context:** Implementing main-people identification (A-018) needs face-IDENTITY embeddings (the existing mediapipe usage only gives bounding boxes), and crowd removal (A-019) needs a generative inpainting backend. Both have a real accuracy-vs-dependency-vs-privacy tradeoff. Asked, the user chose the same shape for both: a lightweight default that works for everyone, plus a configurable heavier/local option for users with a capable machine — mirroring the project's hardware-tier routing philosophy (ADR-0007/0008).
- **Decision:** (1) **Face-ID (A-018):** default backend `gemini` — reuse the already-wired image-embedding route on face crops (zero new dependency; identity accuracy is rough — may split one person across outfits/lighting); optional backend `insightface` — real ArcFace embeddings, selected via the `cast_backend` setting, lazy-imported, model auto-downloads at first use. (2) **Crowd removal (A-019):** default = a **remote image-editing API**; optional = **local generative** (LaMa/SDXL-class) for capable machines, selected via a `crowd_remover_backend` setting. (3) Both are pluggable behind an interface + factory so swapping backends is a config flip, never a code change. (4) Face DETECTION is shared and was made resilient (mediapipe-solutions when present, else OpenCV Haar cascade) because mediapipe 0.10.35 dropped `mp.solutions` — which had also silently disabled M5 privacy-blur on current installs.
- **Alternatives considered:** insightface-only (rejected: forces a heavy dependency + model download on every user for a feature many won't need); local-generative-only for A-019 (rejected: excludes thin-client users the remote default serves); remote-only with no local option (rejected: the user wants an on-device path for privacy/capability).
- **Consequences:** New `media/face_embed.py` (FaceEmbedder protocol + GeminiFaceEmbedder default + InsightFaceEmbedder optional + factory); `media/cast.py` + `pipeline/cast_builder.py` (detect→embed→cluster→group/crowd→coverage); settings keys `cast_analysis_enabled` + `cast_backend`; `_face_detect.py` resilient detection (also fixes privacy-blur on mediapipe 0.10.35); pipeline wires the cast through Stage 4 annotation + Stage 6 coverage report; `cast.json` persisted per project. A-019 backends to be built next on this pattern. Default-backend accuracy is a documented limitation; insightface is the accuracy path.
- **Linked ADRs / items:** A-018, A-019, N-012, ADR-0007, ADR-0008, ADR-0010, ADR-0016.

---

### D-045 — In-app feedback loop: persisted per-phase diagnostics + decision-level feedback, picked up out-of-band by Claude

- **Status:** accepted
- **Date:** 2026-06-14
- **Context:** The user asked for a low-friction way to keep improving video quality by giving feedback on specific automated decisions inside the app, then having Claude pick that feedback up in a later session and act on it. The pipeline already makes richly-inspectable decisions but exposed none of them.
- **Decision:** (1) Persist a `diagnostics.json` per snapshot built from existing artifacts (Stage 4 `filter_log`, the `ArcJudgment`, the `RenderPlan`, the `CastInventory`) — no new LLM calls. (2) Serve it via `GET /api/snapshots/{id}/diagnostics` + a `GET /api/media/{hash}/thumb.jpg` thumbnail endpoint. (3) Capture feedback via `POST /api/feedback` into a `feedback` table (migration 004) + an append-only `~/.impact-crater/feedback.jsonl` mirror. (4) Frontend: a per-phase diagnostics viewer + a per-decision feedback popup on the preview page. (5) `scripts/feedback.py` + a CLAUDE.md protocol are the out-of-band pickup path (N-015). Post-completion (not live-during-execution) for v1 — the data is identical, the complexity is far lower.
- **Alternatives considered:** Live per-phase popups streamed over WS during execution (deferred — same data, much more complex, no extra value for the review-and-improve goal); a free-text "rate this video" box (rejected — too coarse to drive concrete pipeline changes); auto-tuning thresholds directly from feedback (deferred — needs volume + guardrails; the human-in-the-loop Claude pickup is the safe first step).
- **Consequences:** New `pipeline/diagnostics.py`, `api/media.py`, `api/feedback.py`, migration 004, `scripts/feedback.py`; runner writes `diagnostics.json`; frontend gains `DiagnosticsPanel`. The feedback store becomes the durable backlog of user-flagged improvements that future sessions work through.
- **Linked ADRs / items:** A-023, N-015, ADR-0006 (storage), D-042.

---

### D-046 — Feedback loop enhancements: live per-phase diagnostics during execution + page screenshot per feedback

- **Status:** accepted
- **Date:** 2026-06-14
- **Context:** D-045 shipped post-completion diagnostics. The user asked for the per-phase decisions to appear LIVE while the job runs, and for a screenshot of the whole page to be saved with every feedback item. Also clarified that acting on feedback can mean far more than threshold tweaks (new AI modules, new pipeline steps, heuristic rules / custom instructions, model tuning).
- **Decision:** (1) Stream each phase's diagnostics over the job WebSocket as it completes via a new `ProgressReporter.phase_diagnostics` → `JobRegistry.emit_diagnostics` → `"diagnostics"` event; the in-progress page accumulates and renders them in a "Decisions so far" panel with the same feedback popups (using job_id since snapshot_id may not exist until Stage 6). The DiagnosticsPanel was split into a pure `DiagnosticsView` (reused by both the live in-progress view and the post-completion preview view). (2) On feedback submit the frontend captures the whole page with `html-to-image` (toPng, excluding the modal via a `data-ic-skip-capture` filter), POSTs it as a base64 data URL; the backend saves it to `~/.impact-crater/feedback_screenshots/{id}.png` (migration 005 `screenshot_path`), served at `GET /api/feedback/{id}/screenshot.png`. Capture is best-effort and never blocks submission. (3) CLAUDE.md's feedback-pickup section now spells out the full range of changes feedback can drive.
- **Alternatives considered:** Persisting partial diagnostics to disk + polling (rejected — no snapshot_id exists for Stages 4/5, and the WS already carries job progress); server-side screenshotting (impossible — only the browser has the rendered page); a heavier capture lib or native screen-capture API (rejected — html-to-image is small, code-split, and needs no permission prompt).
- **Consequences:** New frontend dependency `html-to-image` (code-split, lazy-imported); `DiagnosticsView` export; live diagnostics on the in-progress page; per-feedback screenshots on disk + a new GET endpoint; migration 005. 390 backend + 35 frontend tests green.
- **Linked ADRs / items:** A-023, D-045, N-015, ADR-0005 (WS), ADR-0006 (storage).

---

### D-047 — In-app developer trackers: feedback tracker (DB-native) + workplan tracker (markdown-read, override-edited)

- **Status:** accepted
- **Date:** 2026-06-14
- **Context:** The user asked for two in-app developer pages: a full-detail feedback/enhancement tracker and a workplan tracker over the project/ MVP/v1/v2 hierarchy, both showing status and an editable priority.
- **Decision:** (1) Feedback tracker is DB-native: added an editable `priority` column (migration 006), `GET /api/feedback/{id}` detail (parsed context + screenshot URL + snapshot diagnostics link), `PATCH /api/feedback/{id}` (status + priority). (2) Workplan tracker READS the canonical `project/` markdown frontmatter (`GET /api/workplan`, repo-root-relative, env-overridable, empty when project/ absent in a packaged install) — it never writes the markdown (work-tracker skill is the only writer, via PRs). Priority edits go to a `workplan_overrides` table; the page shows the effective priority (override ∨ markdown) and a later work-tracker pass reconciles overrides into the markdown (surfaced at `GET /api/workplan/overrides`). Workplan status stays read-only in the app. (3) Both pages link from the dashboard nav.
- **Alternatives considered:** Writing workplan status/priority straight to the markdown from the API (rejected — bypasses the work-tracker PR flow + ownership, creates uncommitted working-tree edits); mirroring the whole workplan into the DB as a second source of truth (rejected — markdown stays canonical per CLAUDE.md); read-only workplan with no priority editing (rejected — the user explicitly wants to change priority).
- **Consequences:** New `api/workplan.py`, feedback API detail/patch, migration 006, frontend `/feedback` + `/workplan` routes + dashboard nav. Priority overrides become a small reconciliation task for work-tracker (documented in CLAUDE.md). 402 backend + 38 frontend tests green.
- **Linked ADRs / items:** A-024, A-023, D-045, D-046, ADR-0002 (work hierarchy), ADR-0006 (storage).
