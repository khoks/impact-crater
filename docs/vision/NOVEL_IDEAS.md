# NOVEL_IDEAS.md — Inventions and novel-mechanism log

> **Status: 11 entries filed (N-001..N-011). N-001..N-007 from E-1.2 vision grooming round 1 (2026-04-26); N-008..N-009 from E-1.3 round-2 architecture grooming (2026-05-02); N-010..N-011 from E-1.3 round-3 architecture grooming (2026-05-03). All approved by the user for public master commit — no patent-priority hold requested.**
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

---

### N-010 — Cross-project user profile + agentic learning loop for media curation (2026-05-03)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Most AI-driven creator tools (image editors, music generators, video editors, narrative generators) treat each user session as **stateless**: every prompt starts from zero, with no memory of what the user has tried before, what they accepted, what they rejected, or what their stylistic tendencies are. The user re-explains their intent every time. Tools that *do* persist preferences typically do so as a flat settings panel (e.g., "default video duration: 90 seconds") rather than as a learned model of the user's behavior across sessions.

In agentic systems specifically, the orchestrator's own decisions — which tool to call, which override to surface, which refinement strategy to choose — are also stateless across sessions. The orchestrator can be cleverly designed but never learns from its mistakes; the same wrong choice gets made the next time the same situation arises.

**The invention.** Build a **persistent, cross-project user profile** that the orchestrator reads from and writes to throughout the user's lifetime use of the product. The profile is **derived from a feedback log** (an append-only event stream of user actions: approve / refine / second-guess-accepted / second-guess-rejected / refinement-succeeded / refinement-failed / pre-filter-overridden / etc.) via periodic LLM-driven re-derivation. The derived profile contains:

- **Style preferences** (preferred target durations, mode bias, music tempo bands, cut pacing, brief motifs, landscape-vs-people bias).
- **Orchestrator priors** (per-override-type acceptance rates, per-refinement-strategy success rates, typical user overrides of system defaults).
- **Narrative patterns** (common arc shapes, preferred openers/closers, recurring music section-to-media mappings).

The profile is read at six call sites in the curation pipeline:

1. **Job creation** — pre-fill suggestions ("based on your past trips, you usually want ~90s videos with energetic music").
2. **Brief parsing** — in-context priors for `parse_user_brief`.
3. **Pre-filter (Stage 4)** — apply learned quality-floor overrides.
4. **Narrative-arc judgment (Stage 5)** — pass narrative patterns as structured context to the Tier-L Opus judge.
5. **Orchestrator second-guess (Stage 6)** — shift the confidence threshold for surfacing overrides based on per-type acceptance rates.
6. **Agentic refinement (Stage 9)** — bias the strategy choice in the thinking step toward historically-successful strategies.

The combination is an **agentic learning loop**: the orchestrator's decisions are tracked, rated by the user's response (approve = success, refine = partial success, reject-override = mistake), and converted into priors that influence future decisions on the same dimensions. No model fine-tuning required; learning happens via in-context conditioning with derived priors.

**Why we think it is novel.** Agentic systems with persistent state are not novel in general (e.g., research agents with vector-store memory, RAG-style retrieval). What is novel here:

- **Cross-*project* learning specifically for media curation.** The unit of state is the user's curation history across many distinct media collections, not a single conversation thread or a single document. Each project has its own brief / scale / target duration / mode, but the user's *preferences over how curation should happen* persist across these.
- **Profile schema designed for a multi-stage pipeline.** Different fields feed different stages (motifs → brief parsing; quality-floor → pre-filter; narrative patterns → arc judgment; second-guess priors → orchestrator behavior). Each stage's prompt template includes only the relevant slice — the profile is not a giant context dump.
- **LLM-driven re-derivation as the learning mechanism.** Rather than fine-tuning or RLHF, the profile is **re-derived from a feedback log** by a Tier-M LLM call after every job-end. Cost is ~$0.005/job; the derivation is structured (frequencies, success rates, motif extraction) rather than free-form summarization.
- **Six distinct read sites, each with stage-appropriate slicing.** Most agentic-memory systems use a single retrieval call; this design integrates profile reads at the right cadence for each pipeline stage.
- **Bounded re-derivation cadence** (incremental every N=10 events, full every N=100) with rotation-friendly schema. Keeps cost predictable and prevents profile drift.
- **One-click reset** as a first-class privacy + UX feature. Users who want a fresh start can wipe the profile + feedback log without affecting projects, snapshots, or person libraries.

The combination — *cross-project profile + LLM-driven re-derivation from a structured feedback log + multi-stage pipeline integration + bounded re-derivation cadence + first-class reset* — applied to a self-hosted media-curation product is, to our knowledge, fresh.

**Where it lives in the system.** [`docs/architecture/ADR-0014-agent-harness-topology.md`](../architecture/ADR-0014-agent-harness-topology.md) §"Cross-project user profile (N-010)." Profile substrate at `~/.impact-crater/profile/profile.json` + `~/.impact-crater/profile/feedback_log.jsonl`. Schema documented in ADR-0014. Re-derivation is a Tier-M call (per ADR-0009 routing). Privacy posture for the profile is in [`docs/architecture/ADR-0016-privacy-posture-defaults.md`](../architecture/ADR-0016-privacy-posture-defaults.md) §"Profile + feedback log privacy."

**Disclosure trail.** First surfaced 2026-05-03 in E-1.3 round-3 grooming as user redirect to Q4 ("we can learn from the chat memories across projects, and build a user profile over time which can help the impact crater suggest ideas to the user itself during new project creations, or also help impact crater to learn from its mistakes the next time around"). User-approved for public master commit on 2026-05-03.

**Linked items.** D-017 (orchestrator), D-022 (refine post-render — feedback events captured here), A-005 (failure recovery — feedback log includes job-cancelled events), A-015 (cost-transparency UI — profile re-derivation cost surfaced), N-009 (agentic refinement — its strategy choice now reads profile priors), ADR-0014 (architectural realization), ADR-0016 (privacy posture for profile data).

---

### N-011 — Privacy-sensitive operation routing (face-data routes to local LLM only when blur-faces is ON) (2026-05-03)

**Status:** proposed — published on master per user instruction (no patent-priority hold)

**Inventor(s):** Rahul Singh Khokhar

**Background.** Hybrid local-and-remote LLM systems route per-call between the local runtime and a remote API based on **cost** and **capacity**: cheap operations go local, heavy or capacity-blocked operations go remote. This is N-002's frame (operation-aware router for cost optimization). Industry implementations (e.g., LangChain routers, Continue's local-first mode) follow the same cost/capacity logic.

**Privacy** as the routing trigger has not, to our knowledge, been packaged as a primary mechanism. The pattern is closer in nature to data-residency policies in enterprise software (route data of class X through region Y) than to cost-optimizing LLM routing.

**The invention.** Make the **per-data-sensitivity** routing decision a first-class mechanism in the LLM router. Each operation declares a `privacy_class` (e.g., `face_data`, `visual_only`, `derived_metadata`, `text_only`). Each provider declares a `eligibility_for_class` set (which classes it's allowed to handle, declared by the user as policy). When the user's privacy posture changes (e.g., toggles "blur faces" ON), the router dynamically removes remote providers from the eligibility set for the affected class (`face_data` becomes local-LLM-only). If a local provider exists and is eligible, the operation routes there with the unblurred image. If no local provider is available, the operation **degrades gracefully** — the call site has a defined "skipped operation" path that produces a degraded but non-broken result, and the UI surfaces the consequence to the user.

The system is built **plug-and-play in the architecture from MVP** even when the local LLM itself is a v1 deliverable: the routing config has the hooks; the providers' eligibility map is declared; the degradation path is implemented. v1's local-LLM runtime drops in without any code changes for the privacy-routing feature to become functional.

**Why we think it is novel.** Per-cost routing exists. Per-capacity routing exists. **Per-privacy-class routing as a first-class mechanism in an LLM router** — with declarative per-operation privacy classes, per-provider eligibility sets, and a documented graceful-degradation path for skipped operations — is fresh.

Specific novel ingredients:

- **Per-operation `privacy_class` annotation** in the routing config. Operations are tagged with what kind of sensitive data they handle, not just their cost tier.
- **Per-provider `eligibility_for_class` declaration.** The user's privacy posture filters this dynamically; the static config gets pruned at runtime.
- **Graceful degradation** when no eligible provider exists — the call site has a `skipped` mode that produces a degraded result (e.g., metadata extraction without `recognized_persons`), and downstream stages handle missing fields. Most routing systems either error out or fall back silently to a less-suited provider; the explicit-skip-with-degradation is intentional.
- **Plug-and-play hook design.** The MVP architecture is correct without the local-LLM runtime; v1 drops in the runtime and the privacy-routing feature becomes functional with zero code changes.
- **Combination with the user-toggle-driven dynamic eligibility** (rather than static deployment-time policy). Users can flip "blur faces ON" mid-session; the router consults the current posture on each call.

The mechanism complements (does not replace) N-002's cost-optimizing operation-aware router; both will share router infrastructure in v1. N-011 is the **policy** axis (privacy → eligibility), N-002 is the **performance** axis (cost/capacity → optimal-routing).

**Where it lives in the system.** [`docs/architecture/ADR-0016-privacy-posture-defaults.md`](../architecture/ADR-0016-privacy-posture-defaults.md) §"Privacy-sensitive operation routing (N-011)." Extends the routing-config schema in [`docs/architecture/ADR-0007-remote-llm-abstraction.md`](../architecture/ADR-0007-remote-llm-abstraction.md). Local-LLM destination per [`docs/architecture/ADR-0008-local-llm-runtime-slot.md`](../architecture/ADR-0008-local-llm-runtime-slot.md) (v1). Person-library context per [`docs/architecture/ADR-0010-media-pipeline-framework.md`](../architecture/ADR-0010-media-pipeline-framework.md).

**Disclosure trail.** First surfaced 2026-05-03 in E-1.3 round-3 grooming as user redirect to Q7 ("if the user turns it on, and if the user has local llm connected, then we can suggest to offload the face related functionalities to local llm and build it like that in a plug and play manner to begin with, in case user wants to 'set it on for remote but use local'"). User-approved for public master commit on 2026-05-03.

**Linked items.** A-002 (privacy posture — N-011 is its enforcement mechanism), D-016 (remote-first routing default — privacy-routing is the per-data-class deviation), N-002 (operation-aware router future — sibling concept; both share router infra in v1), N-008 (person library — recognition op is `face_data`-classed), ADR-0007 (routing dispatch — extended here), ADR-0008 (local-LLM destination), ADR-0010 (face-detection-only library used for blur masking; person library tools), ADR-0016 (architectural realization).

---

### N-012 — Auto-derived trip cast with group-vs-crowd inference and coverage-aware curation (2026-06-11)

- **Date conceived:** 2026-06-11 (user session — dump-and-forget trip workflow grooming)
- **Public commit risk:** this PR publishes the idea on a public repo; user has accepted public-by-default posture for this project (CLAUDE.md "Decisions locked"). Flagged per protocol.
- **Mechanism:** Before curation, the app scans the full media set: face detection (mediapipe) on analysis renditions → face-embedding clustering into unique persons → each cluster scored by recurrence breadth (appearance count × distinct time-windows × distinct locations/events). High-recurrence clusters are inferred as "the group" (the people the trip is ABOUT); low-recurrence clusters are background crowd. The resulting cast inventory becomes curation context: Stage 5 receives per-candidate cast annotations ("contains: persons 1,3 of 6-person group"), and Stage 6 emits a coverage report — which group members are over/under-represented in the selected timeline, with one-click "include a shot of X" repair. The inventory can also auto-seed N-008's manual person library, demoting enrollment to confirmation.
- **What's novel:** The recurrence-breadth heuristic for group/crowd separation (time-windows × locations, not raw face count — a tour guide appearing 40 times at ONE location stays crowd; a shy cousin appearing 6 times across 5 days is group), and closing the loop from cast inventory into selection-time coverage repair. Adjacent prior art (Google Photos people clustering, Apple Memories) clusters faces for search/albums but does not do group-inference-driven coverage-aware video curation.
- **Prior art known:** Google Photos face grouping; Apple Photos People album; academic face-clustering literature. Coverage-aware automatic video curation across a face-derived cast: unknown.
- **Linked items:** A-018, A-019 (consumer), N-008 (library it seeds), ADR-0016 / N-011 (face-data privacy routing applies).

---

### N-013 — Media-density-driven package planning (trip → artifact-set allocation) (2026-06-11)

- **Date conceived:** 2026-06-11 (user session — "the ultimate feature" grooming)
- **Public commit risk:** this PR publishes the idea on a public repo; user has accepted public-by-default posture (CLAUDE.md). Flagged per protocol.
- **Mechanism:** A planner above the single-artifact pipeline turns one media dump into a coherent multi-artifact package. (1) Segment the trip: cluster all media by capture-time gaps + EXIF GPS + content embeddings into events/locations/themes. (2) Score each cluster on media density (count × duration), quality distribution, and distinctiveness. (3) Allocate artifacts by density: clusters above a richness threshold earn a dedicated Story Video; thin clusters merge with temporal neighbors into combined videos ("Bryce hike + evening drive"); standout moments (quality × uniqueness peaks) queue as reel/short candidates; every cluster contributes weighted material to one overall trip video and one montage. (4) Emit the package as N artifact briefs (brief text synthesized per cluster + media subset + duration + mode + platform), each executed by the existing pipeline, all sharing ONE analysis pass via the content-addressed cache (N-007) so analysis cost is paid once for the whole package. (5) Single package-approval surface; per-artifact approve/refine/publish.
- **What's novel:** The density-driven granularity decision — the planner decides HOW MANY artifacts a trip deserves and WHERE the boundaries fall from the media's own evidence (density/quality/distinctiveness), rather than fixed templates ("one video per day") or manual selection. Combined with brief synthesis per cluster and cache-shared analysis economics, the package becomes a planned portfolio, not a batch of independent jobs.
- **Prior art known:** Google Photos Memories / highlight reels (template-driven, single-artifact, no density-driven allocation); GoPro Quik auto-edits (single video). Portfolio-level density-driven artifact allocation with per-artifact narrative briefs: unknown.
- **Linked items:** A-020, N-005/A-012 (v1.2 multi-output seed), N-001 (per-artifact judge), N-007/A-011 (shared-analysis economics), D-042 (sequencing gate), ADR-0013 (multi-platform publish).

---

### N-014 — Multi-source capture-time reconciliation with confidence tagging (2026-06-11)

- **Date conceived:** 2026-06-11 (user session — "identify the timeline from filenames and timestamps, which can be misleading")
- **Public commit risk:** this PR publishes the idea on a public repo; user has accepted public-by-default posture (CLAUDE.md). Flagged per protocol.
- **Mechanism:** Each media file's capture time is resolved by trying three sources in reliability order and recording which won: (1) EXIF DateTimeOriginal — embedded by the camera at the shutter, canonical; (2) a filename-encoded timestamp parsed by an ordered battery of device/app patterns (Pixel `PXL_YYYYMMDD_HHMMSSsss`, `IMG_/VID_`, WhatsApp `IMG-YYYYMMDD-WA####`, Signal, screenshots, dashed) — reliable but occasionally a wrong device clock or a rename; (3) file mtime — last resort, since sync/download resets it. The winner's `source` and a numeric `confidence` (1.0 / 0.8 / 0.4 / 0.0) travel with the timestamp so every downstream consumer — the narrative judge, burst-window dedup, trip segmentation — can weigh how much to trust the ordering rather than treating all timestamps as equally true. EXIF GPS is decoded in the same pass.
- **What's novel:** Treating capture time as a *reconciled, confidence-tagged* signal rather than a single trusted field, specifically so a downstream planner can decide when to follow chronology and when to override it. The user's own insight — that filenames and timestamps "can be misleading sometimes" — is encoded as first-class confidence rather than ignored. Photo-management tools read one source (usually EXIF) and treat it as ground truth; the reconciliation-with-confidence-for-planning combination is the non-obvious part.
- **Prior art known:** ExifTool / Photos apps read EXIF DateTimeOriginal; many tools fall back to mtime. Confidence-tagged multi-source reconciliation feeding a curation planner: unknown.
- **Linked items:** A-021, A-017 (time-windowed dedup), A-018 (recurrence breadth), A-020 (trip segmentation), D-043.

---

### N-015 — Decision-level feedback loop with out-of-band Claude pickup (2026-06-14)

- **Date conceived:** 2026-06-14 (user session — "a feedback mechanism via which the app keeps getting enhanced when I give you inputs")
- **Public commit risk:** this PR publishes the idea on a public repo; user accepts public-by-default posture (CLAUDE.md). Flagged per protocol.
- **Mechanism:** Every deterministic + LLM decision the curation pipeline makes is persisted as an inspectable per-phase diagnostics document tied to the exact media it concerns. The user reviews these in-app and attaches a structured verdict (correct / incorrect / should-differ) + note to any single decision. That feedback is stored both in a queryable table and an append-only JSONL, and a CLI surfaces it to a *separate AI coding agent* (Claude Code) which reads the feedback, makes the corresponding code/prompt/threshold change, and marks the item addressed — closing a loop from "user disagrees with this specific automated decision" to "the system's behavior changed", without the user writing a bug report.
- **What's novel:** The bridge between an end-user product's decision-level feedback and an AI software-engineering agent's backlog. Most apps collect feedback for humans to trIage; here the feedback is shaped (phase + decision_ref + media + context snapshot) specifically so an autonomous coding agent can act on it directly, and the loop is explicitly designed around that handoff (the JSONL + `scripts/feedback.py` + the CLAUDE.md pickup protocol). It makes the user's individual taste the training signal for the app's curation behavior, applied through code changes rather than model weights.
- **Prior art known:** RLHF / thumbs-up-down feedback (aggregate, model-weight-directed); analytics event capture; bug-report tools. Decision-level product feedback routed to an AI coding agent as actionable engineering tasks: unknown.
- **Linked items:** A-023, D-045, N-010 (cross-project profile — a complementary learning loop), D-042.
