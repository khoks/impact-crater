# NOVEL_IDEAS.md — Inventions and novel-mechanism log

> **Status: 9 entries filed (N-001..N-009). N-001..N-007 from E-1.2 vision grooming round 1 (2026-04-26); N-008..N-009 from E-1.3 round-2 architecture grooming (2026-05-02). All approved by the user for public master commit — no patent-priority hold requested.**
>
> ⚠️ **Public-repo warning.** This repository is public from day 1 (decision D-005). A novel idea committed here is *publicly disclosed* the moment it lands on `master`. If you want to preserve patent options for an idea, **file an N-NNN entry in a feature branch first, talk to counsel, and only then merge the branch to master.** The `knowledge-curator` skill defers to this rule by opening a PR rather than auto-merging.

---

## What goes here

This file is the project's record of **novel mechanisms, non-obvious combinations, and potentially-patentable concepts**. Distinguish from the decision log:

- Decisions (in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)) are choices between known options.
- Inventions are *new mechanisms* — algorithms, system architectures, product shapes that may not exist in the public literature.

The skill's job is to flag candidates and preserve the chronology. **The skill does not assess legal patentability** — that is a follow-up the user does, possibly with counsel.

---

## Detection heuristic — when to file an `N-NNN`

Treat an idea as a candidate invention when **any** of the following hold:

- The user describes a mechanism that they cannot easily point to as already existing in a product they know.
- A combination of two or more techniques is being used together in a way the user thinks is unusual.
- An algorithm is being designed (not selected) — choosing how a quality score is computed, how a narrative arc is built, how the local/remote LLM router decides.
- The user explicitly says "this might be patentable" or "I don't think anyone is doing this."
- The discussion produces a rule, threshold, or training signal that is bespoke to this product and not lifted from a paper.

If you're unsure between a decision and an invention, file both: a `D-NNN` for the choice, and an `N-NNN` for the underlying mechanism.

---

## Entry format

```markdown
### N-001 — <short title> (YYYY-MM-DD)

**Status:** proposed | filed-internal | filed-external | published | abandoned

**Inventor(s):** Rahul Singh Khokhar (default)

**Background.** What problem this addresses, and what existing approaches do.

**The invention.** The new mechanism, in plain language. Be precise. Include the steps, the inputs and outputs, and any thresholds or learned components.

**Why we think it is novel.** What makes this non-obvious. Briefly compare to the closest existing approach you know of.

**Where it lives in the system.** Pointer to the doc / module / Story where the implementation will land.

**Disclosure trail.** Date of first session it appeared, link to the conversation if available, link to the merge commit that first made it public (if/when public).
```

Number monotonically (`N-001`, `N-002`, …). Never renumber. Never delete an entry — supersede it with a new entry instead.

---

## Entries

### N-001 — Hybrid pipeline with explicit narrative-arc judgment stage (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Most photo / video curation systems score and select per-image (or per-frame) using a quality signal, then either deduplicate or rank. Highlight-detection literature in research adds learned per-clip importance scores. Neither dimension reasons about the *narrative shape* of the candidate set as a whole.

**The invention.** As the final stage of the hybrid curation pipeline (D-009), after deterministic pre-filter (perceptual-hash → quality floor → scene segmentation) and after rich per-photo / per-scene metadata extraction, run a dedicated **narrative-arc judgment** call. The input is the full candidate set with metadata; the output is an ordered subsequence chosen and ordered to satisfy a narrative shape (e.g. setup → escalation → climax → denouement; or for a music-video sub-mode per D-010, music-section-aligned beats).

The narrative judge is implemented as a multimodal-LLM call with structured input (the candidate metadata table) and structured output (an ordered subsequence with per-pick rationale). It operates over the *whole candidate set* rather than scoring items independently — so it can refuse a high-quality photo because it duplicates the narrative role already filled by another, or accept a lower-quality photo because it is the only candidate that establishes a needed beat.

**Why we think it is novel.** The narrative-shape-as-an-explicit-stage formulation is research-adjacent (story summarization, video summarization with arc constraints exist as research topics), but the **packaged combination** — hybrid pipeline + LLM-as-narrative-judge + per-pick rationale + per-mode arc template (standard / music-video) in a consumer media app — is not, to the inventor's knowledge, deployed in current consumer products.

**Where it lives in the system.** Will land in the curation engine module. Specified by D-009; concrete implementation belongs to E-1.3 architecture grooming and a future Story under the Curation Engine epic.

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-A in the round-1 plan. User-approved for public master commit on 2026-04-26.

**Linked items.** D-009, D-010, A-013.

---

### N-002 — Operation-aware LLM router (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Existing local-vs-remote LLM routing systems route at the *call* boundary: a whole inference call is either local or remote, decided by a policy looking at provider availability, cost, latency, or quota. Cascade routing (cheap-model-first, escalate to large-model on uncertainty) exists in research but still routes whole calls.

**The invention.** Route at the **sub-operation** boundary inside a single curation pass. The orchestrator (D-017) decomposes a curation job into typed sub-operations: *embed*, *caption*, *scene-segment*, *quality-score*, *metadata-extract*, *narrative-judge*, *render-prep*. Each sub-operation has a declared compute profile (latency-bound vs. throughput-bound; semantic richness required; sensitivity to model quality). The router maps each sub-operation to a target — local model class, specific remote provider, or a sub-cascade — using a per-operation policy.

Concretely: `embed` and `quality-score` may run on a local 7B model; `metadata-extract` may run on a remote VLM (Claude / GPT-4o / Gemini); `narrative-judge` (N-001) may run on the largest remote model the user's quota supports. The same job spans multiple providers and multiple modalities of model in one logical pass.

**Why we think it is novel.** The per-sub-operation routing granularity inside one curation pass — combined with a typed sub-operation decomposition that comes from the orchestrator's tool schema — is, to the inventor's knowledge, fresh. Closest prior art is the cascade-routing literature (which still routes per-call) and the multi-tool-call agent patterns (which don't formalize per-tool routing policy).

**Where it lives in the system.** Will land between the orchestrator (D-017) tool dispatch layer and the model-call boundary. Specified informally by D-016 (gates the local-first v1 commitment). Will be a Story under E-1.3 architecture or under a future LLM-Routing epic.

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-B in the round-1 plan. User-approved for public master commit on 2026-04-26.

**Linked items.** D-009, D-016, D-017, N-001.

---

### N-003 — Project as a git-like versioned artifact (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Media-editing apps typically present projects as mutable workspaces with a linear undo/redo stack. Versioning, when present, is often a separate concept (template snapshots, save-as). git's snapshot-and-branch model is ubiquitous in code but rarely applied to media projects.

**The invention.** A project (A-001) is a content-addressed, versioned tree. Each *preview* of a Story Video is a snapshot node (referencing input media hashes per A-010, the orchestrator's tool-call trace, and the rendered artifact hash). Each *approve-and-publish* event is a publish node tagged with a YouTube video ID and timestamp (per A-003). Each *refine* (D-011 refine-loop, when on per D-020) creates a branch from the current snapshot. Multi-version comparison (A-006) becomes a diff between two snapshot nodes — falling out for free.

Concretely, the project's persistent state is a DAG of snapshots; the UI exposes "history" naturally (chronological), "branches" (parallel refines), and "publish events" (decorated nodes). Users can revert to any snapshot, fork from any snapshot, and re-render from any snapshot.

**Why we think it is novel.** Mildly novel as a media-app pattern; clearly inspired by git, but applying the model to media projects with first-class publish-event nodes and refine-as-branch semantics is, to the inventor's knowledge, not present in current consumer media tools.

**Where it lives in the system.** The project / job storage layer (A-001, A-005). Concrete schema and implementation are deferred to E-1.3 (storage decisions) and a future Story under the Project Model epic.

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-C in the round-1 plan. User-approved for public master commit on 2026-04-26.

**Linked items.** A-001, A-003, A-005, A-006, D-011, D-020.

---

### N-004 — Reference-media style fingerprint extraction (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Style-transfer for video editing exists in research and in some niche tools (e.g., applying the look of a reference film). Most published work targets *render-time* style application — color grading, LUT transfer, stylization filters.

**The invention.** Extract a structured, **instructable style descriptor** from any reference media (uploaded files, public URLs subject to ToS, prior projects). The descriptor is multi-axis: color palette (dominant colors, contrast curve), pacing (cut frequency, scene-length distribution), framing (composition tendencies — close vs. wide, subject placement), music feel (tempo, mode, energy if music is present), narrative shape (arc template extracted via N-001-like analysis applied to the reference).

The fingerprint is then applied to the **curation stage** (D-009) — not just the render stage — by adding a "style match" objective to the narrative judgment (N-001). The judge is told: "Pick and order the candidate set so the resulting Story Video has a fingerprint close to this reference." This makes the style influence the *what gets included*, not just the *how it looks at render time*.

**Why we think it is novel.** Style transfer at render time is well-explored. The novel angle is the **fingerprint-as-instructable-vector applied to curation**, not just render. To the inventor's knowledge, no current consumer media tool extracts a structured style descriptor from a reference and uses it as a curation objective.

**Where it lives in the system.** Reference-media style learning feature (A-014). Implementation lands in v1; specified informally now. Concrete model choice and descriptor schema deferred to E-1.3.

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-D in the round-1 plan. User-approved for public master commit on 2026-04-26.

**Linked items.** A-014, D-009, N-001.

---

### N-005 — Live-job pattern (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold) — **strongest novelty candidate**

**Inventor(s):** Rahul Singh Khokhar

**Background.** Existing photo / video curation tools operate in batch mode: user finishes a trip, dumps the media in, and processes it after the fact. There are real-time photo-stream tools (cloud uploads, auto-organize) but they organize and tag — they do not curate-and-publish artifacts during the event.

**The invention.** A "live job" is a long-lived job set up *before* an event begins. It declares one or more outputs (per-location reels, an overall YouTube Story Video, collages per mini-event), each targeting a platform with a publish gate (D-020). The job opens an ingest source (smartphone camera roll watcher, OneDrive folder, iCloud / Google Photos shared bucket) and listens for new media. As media arrives, the curation pipeline runs incrementally — updating the candidate set, refreshing per-output narrative arcs, queuing per-output render passes. The job can publish *during* the event when a per-output trigger fires (e.g., "render and publish a daily reel every evening", "publish the collage when a new location is detected").

The job is conversationally configured at creation. The orchestrator (D-017) negotiates the multi-output declaration with the user in natural language ("How many days? What outputs do you want? Which platforms?") and persists the resulting plan as part of the project state (N-003).

**Why we think it is novel.** Strong novelty candidate — the inventor is not aware of a consumer-app product that does *all* of: continuous-ingest from cloud / camera-roll sources, multi-purpose (multiple outputs from one source set), multi-platform (per-output platform targeting), *during-event* publish gates, and conversationally configured at the start of a long event.

**Where it lives in the system.** Live-job feature (A-012) — v1 commitment. The MVP architecture must leave a clean feature flag for this (per the A-012 verdict): the project / job model and the orchestrator are designed for one-or-many jobs per project and one-or-many outputs per job from MVP day one.

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-E in the round-1 plan. User-approved for public master commit on 2026-04-26 ("publish all N-cands on public, doesn't matter").

**Linked items.** A-001, A-012, D-017, D-019, D-020, N-003.

---

### N-006 — Effort-level UX with agentic max-permissible recommendation (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Tier-based UIs (free / pro / enterprise) and cost calculators (per-API-call price estimators) exist independently. Some media tools surface a quality / time / cost dial. None, to the inventor's knowledge, packages the combination as an agentic surface that reads the user's actual configuration and reasons about feasibility.

**The invention.** The product defines 3–5 effort levels (D-013) (e.g., L1 ≈ 10 photos + 1 short video; L5 ≈ 10000 photos + 500 long videos). The orchestrator (D-017), at job-creation time, reads the user's LLM configuration (local model class, remote provider quotas) and **computes the max permissible level** for the job — the highest level the configuration can support within the wall-clock ceiling (D-012, D-014). The recommendation is surfaced after task details + media selection.

When the user requests a level beyond max permissible but within possible, the orchestrator generates a **transparent cost explanation** ("this will cost approximately $X in remote-API charges and take ~Y hours; here's why"). When the user requests a level beyond what the current config can support at all, the orchestrator generates an **upgrade-path explanation** ("to support L4, you would need either provider tier T or local model class M; here's how to configure it"). Both explanations are agentic / GenAI-generated, not static templated copy.

**Why we think it is novel.** Mildly novel as a packaged UX pattern. Components exist in isolation (cost calculators, tier UIs, configuration coaches). The combination — agentic max-permissible recommendation + transparent cost projection + agentic upgrade-path explanation — for a media-AI app is, to the inventor's knowledge, fresh.

**Where it lives in the system.** Effort-level UX feature (A-015). MVP ships L1–L3 + recommendation; full v1 ships L4–L5 + cost-transparency UI + upgrade-path agent. The recommendation engine sits inside the orchestrator (D-017).

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-F in the round-1 plan. User-approved for public master commit on 2026-04-26.

**Linked items.** A-004, A-015, D-012, D-013, D-016, D-017.

---

### N-007 — Cross-job content-addressed analysis cache schema (2026-04-26)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Content-addressed caching is a well-established engineering pattern (git, Bazel, ccache, etc.). Per-asset analysis caches (e.g., remember the embedding of a photo) appear in image-search systems. What is less well-explored is a **schema for partial-result reuse across heterogeneous downstream tasks** — i.e., reusing an embedding even when the task-context-specific tags must be recomputed for a new job.

**The invention.** The cache (A-011) is keyed by the content hash (A-010) of the source media. For each cached entry, the schema separates results by **reuse class**:

- *Universal* — embeddings, perceptual hashes, dedup signals; always reusable.
- *Model-versioned* — captions, quality scores; reusable so long as the underlying model version matches; auto-invalidated on model bump.
- *Task-context-specific* — tags generated under a specific user-task brief; not reused across jobs by default but flagged as candidate priors that can be re-scored cheaply.
- *Time-bounded* — anything where the value drifts (e.g., privacy-policy-derived flags); refreshed on access if older than a configured TTL.

The cache exposes a **partial-hit semantics**: a job querying a hash gets back the universal + model-versioned entries (free), can opt to consume task-context-specific entries as priors, and triggers re-extraction only for what's missing.

**Why we think it is novel.** As an engineering pattern in isolation, content-addressed caching is not novel. The novelty here is the **reuse-class taxonomy + partial-hit semantics** specialized for media-curation pipelines, plus the explicit treatment of task-context-specific results as cheap-rescoreable priors.

**Where it lives in the system.** The cache layer underneath the metadata-extraction stage (D-009). MVP-lite version (A-011 phase tag) implements universal + model-versioned classes; full v1 implements all four classes with partial-hit semantics. Concrete schema lands in E-1.3.

**Disclosure trail.** First surfaced 2026-04-26 in E-1.2 vision grooming round 1. Filed as N-cand-G in the round-1 plan. User-approved for public master commit on 2026-04-26.

**Linked items.** A-010, A-011, D-009, D-016.

---

### N-008 — Vision-LLM face recognition via labeled reference collage (2026-05-02)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Standard face-recognition stacks (FaceNet, InsightFace, DeepFace, dlib's face-recognition) build identity vectors from face crops, then compute embedding distance against a gallery of known faces to identify matches. These stacks require a separate model file, are sensitive to angle/lighting variation in the gallery photos, and don't integrate with the LLM-driven metadata-extraction infrastructure already running in this product per ADR-0007 / ADR-0009.

The natural alternative — "ask the vision LLM 'is this Alice?'" — fails because the vision LLM has no internal model of "Alice"; it's an open-domain visual reasoner, not an identity-database.

**The invention.** Build a per-person library where each person is associated with **N unique face photos** (default N = 5; range 3–10 per the ADR-0010 cap). At face-recognition time, **construct a single labeled reference collage** — a tiled image that grids together the N face photos for each person, with each person's display name overlaid as a label above their strip. Pass this collage as a *second image input* to the vision LLM alongside the photo being analyzed. The LLM is asked, via a structured-output schema, to identify which (if any) of the labeled persons in the reference collage appear in the photo, with per-match confidence scores.

The mechanism leverages the LLM's open-domain visual reasoning to do identity threading without an embedding model. The collage acts as in-context evidence: the LLM sees direct photographic examples of each person from multiple angles/lightings and reasons about identity holistically, the way a human would.

**Why we think it is novel.** "Reference image as in-context grounding for vision-LLM identification" is an emerging pattern in research, but the specific combination here is fresh:

- **Multiple reference photos per person** (collage, not a single canonical photo) — captures intra-person variability the LLM can use for matching robustness.
- **Labeled collage as a single second-image input** — fits in a single LLM call alongside the analyzed photo; no per-person separate calls.
- **Structured-output schema with confidence scores** — produces the same shape as embedding-distance recognition does, slot-compatible with downstream pipeline.
- **Cache-correct integration** — the cache key includes a `library_version_hash` so collage changes invalidate exactly the relevant cached extractions and nothing else; reuses N-007's reuse-class taxonomy.
- **Zero dependencies beyond the already-running LLM stack** — eliminates an entire class of engineering work (face-recognition library install, model weights, runtime).

What is *not* novel here: the general idea of in-context-learning for identification has appeared in research; what's novel is the specific recipe (labeled collage + structured output + cache-correct integration) for an MVP-class media-curation product.

**Where it lives in the system.** ADR-0010 §"Face detection + person-library recognition." The person library schema is in ADR-0006 (`persons` + `person_face_photos` SQLite tables). The recognition call site is ADR-0011 Stage 3 rich metadata extraction; the collage is constructed once per `library_version_hash` and cached alongside other media-pipeline artifacts.

**Disclosure trail.** First surfaced 2026-05-02 in E-1.3 round-2 grooming as user redirect to Q3 ("vision-LLM only" extended with the optimization idea). User-approved for public master commit on 2026-05-02.

**Linked items.** A-002 (privacy posture — face data flows through the LLM client), D-009 (rich metadata schema gains `recognized_persons` field), ADR-0010 (architectural realization), ADR-0011 (Stage-3 call site), N-007 (cache schema includes library_version_hash).

---

### N-009 — Agentic refinement with custom plan generation (2026-05-02)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** "Refine my output" is a standard pattern in generative-AI products: the user reviews a result, types a natural-language adjustment, and the system tries again. Common implementations:

- **Re-run-with-prompt:** the user's message is appended to the original prompt; the model re-generates from scratch. Wastes any work that didn't need changing; ignores per-stage costs in pipelined systems.
- **Direct manipulation:** the system exposes structured editing controls (sliders, drag-and-drop) and the user edits the output directly. Avoids re-running but requires the user to do the work themselves; doesn't leverage AI judgment.
- **Single-stage re-run:** the system re-runs only the stage closest to the output. Cheaper but doesn't help when the refinement requires upstream changes (e.g., re-extracting metadata for items the pre-filter dropped).

None of these match how a thoughtful human collaborator would handle "more landscape, less faces" on a curation pipeline: a person would *think* about what the message implies (do we have landscape photos that got filtered out? do we need to re-extract metadata? is this a placement problem or a selection problem?), pick the cheapest viable approach, and explain their reasoning.

**The invention.** Implement the refinement loop as an **agentic thinking step** that produces a **per-refinement custom plan**. The orchestrator (running on a Tier-M LLM) receives:

- The user's natural-language refinement message.
- The current state of the pipeline (`ArcJudgment`, `RenderPlan`, `SecondGuessResult` history, the user's brief, target_duration, mode, music spec).
- The full Stage-3 rich metadata for the entire input set (not just the candidate set — for "more landscape" the orchestrator may want items the pre-filter previously dropped).
- A toolkit of pipeline tools: `re_run_stage_5_with_addendum`, `re_extract_metadata_for`, `re_run_pre_filter_with_overrides`, `request_user_input`, `explain_why_not_possible`.

The orchestrator's thinking step decides between five strategies:

1. **Partial-fix-via-plan-edit** — re-run Stage 5 with a brief addendum reflecting the user's NL message. Cheapest; reuses Stage 1–4 cache fully.
2. **Partial-fix-via-stage-3-rerun** — re-extract metadata for items the orchestrator believes are missing relevant info (e.g., "more landscape" might mean re-tagging items the prior extraction missed).
3. **Full-reprocess** — re-run from Stage 4 onward.
4. **Request-additional-input** — the refinement requires something the orchestrator can't produce from current inputs (e.g., "use a different music file" → ask the user to upload one).
5. **Explain-why-not-possible** — some refinements aren't realizable with current media; the orchestrator explains rather than producing a worse result.

The chosen plan is recorded on the new snapshot, the action executes, and a new render is produced. The thinking-step's reasoning is itself logged, surfaced to the user via the cost-transparency UI ("I chose partial-fix-via-plan-edit because the metadata already includes landscape tags; no re-extraction needed").

**Why we think it is novel.** Agentic systems with tool calls are well-established. What is novel here:

- **Refinement as planning, not as parameter-tweak.** The orchestrator chooses *how* to refine, not just *what* parameters to change. This sidesteps the brittleness of fixed refinement protocols.
- **Tools cover the entire pipeline upstream of the failure point** — the orchestrator can climb back to Stage 3 (re-extract metadata), Stage 4 (re-pre-filter), or Stage 5 (re-judge with addendum) per the cheapest viable strategy. Most products only re-run the last stage.
- **Cost-aware strategy selection.** The orchestrator's prompt biases toward cheaper strategies (cache-friendly), upgrading only when partial fixes would not work. Cost-envelope ratio: typical refinement costs ~10% of a full job vs a re-run-with-prompt approach.
- **Per-snapshot persistence of the chosen plan + reasoning** — supports a v1 learning loop where successful refinement strategies inform future thinking-step priors.
- **Bounded loop with explicit "give up" path.** Max 10 turns; `explain_why_not_possible` is a first-class outcome; prevents the system from churning on contradictory user requests.

The combination of "agentic plan generation over a multi-stage pipeline with cost-aware strategy selection and bounded thinking loop" applied to media curation is, to our knowledge, fresh.

**Where it lives in the system.** ADR-0011 Stage 9. Tools formalized in ADR-0014 (round 3, agent harness). Per-snapshot persistence per ADR-0006 (`snapshots/{id}/refinement_plan.json`).

**Disclosure trail.** First surfaced 2026-05-02 in E-1.3 round-2 grooming as user redirect to Q6 ("a thinking step which will create a new custom plan of either reprocessing the whole thing or to just make changes to the final result using the tools and AI skills at hand"). User-approved for public master commit on 2026-05-02.

**Linked items.** D-009 (curation pipeline shape — N-009 is its refinement substrate), D-011 (job model — refinement creates a new snapshot), D-017 (orchestrator — N-009 lives in the orchestrator's tool-call surface), D-022 (refine offered post-render alongside Approve), A-005 (failure recovery — bounded loop is its own kind of recovery), A-006 (multi-version comparison — refinement chains build the snapshot graph), A-015 (cost-transparency UI — thinking-step reasoning surfaced), ADR-0011 (architectural realization at Stage 9), ADR-0014 (round 3 — orchestrator tool surface).
