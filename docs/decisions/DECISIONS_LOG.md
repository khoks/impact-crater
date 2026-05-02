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







