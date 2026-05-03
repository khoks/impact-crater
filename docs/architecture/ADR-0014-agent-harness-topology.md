# ADR-0014 — Agent harness topology + cross-project user profile

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-03
**Phase:** scaffolding

## Context

D-017 fixed the MVP harness as a **single orchestrator with structured tool calls**, deferring multi-agent (planner + media-analyst + editor + publisher) to v2. Rounds 1 + 2 introduced concrete tools (orchestrator second-guess; agentic refinement; music-duration analysis) and concrete operations (LLM operations from ADR-0007). Round 3 consolidates the tool surface, locks the reasoning model, and — per user redirect Q4 — introduces the **cross-project user profile + agentic learning loop** that turns the orchestrator from a per-job stateless agent into one that gets sharper over the user's lifetime use of the product.

The Q4 redirect (verbatim, 2026-05-03):

> "we can learn from the chat memories across projects, and build a user profile over time which can help the impactcrater suggest ideas to the user itself during new project creations, or also help impactcrator to learn from its mistakes the next time around."

This filed as **N-010** (cross-project user profile + agentic learning loop). It's a meaningful expansion beyond the original "no chat-memory beyond current loop" proposal — the orchestrator now has a persistent, cross-project memory it reads + writes.

Other round-3 user redirects:

- **Q3 failure-mode UX** = three actions (continue / abandon / restart). Manual-override deferred to v1.

## Decision

### Topology

**Single orchestrator class** (`Orchestrator`) running on Tier-M Claude Sonnet 4.7 per ADR-0009 `orchestrator_reasoning` operation. Lives in the FastAPI process per ADR-0005. Per-job state is the snapshot graph (ADR-0006). Cross-project state is the **user profile** (new, this ADR).

Multi-agent harness (planner + media-analyst + editor + publisher) remains v2 per D-017.

### Tool registry

Each tool implements:

```python
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict          # JSON Schema for input
    output_schema: dict         # JSON Schema for output
    idempotency_class: Literal["free", "project_mutating", "external_side_effect"]

    async def execute(self, input: dict, context: OrchestratorContext) -> dict: ...
```

`idempotency_class` controls confirmation behavior:

- **`free`** (read operations): no confirmation needed; can be retried freely.
- **`project_mutating`** (writes to snapshots / persists state): no per-call confirmation but the orchestrator second-guess pass (per ADR-0011 Stage 6) applies.
- **`external_side_effect`** (publish to platform / charge LLM API quota): requires explicit user confirmation per call. The orchestrator surfaces a confirmation prompt; tool only executes after the user clicks through.

### Consolidated tool surface (rounds 1 + 2 + 3)

Documented as the canonical list. Adding a new tool = update this section + register in the tool registry.

#### LLM operations (ADR-0007 / ADR-0009)

Routed via `LLMRouter` to the appropriate provider+model per the static config:

- `embed_image`, `embed_text`
- `caption_image`, `caption_video_scene`
- `score_image` (multi-dimension)
- `extract_metadata_image`, `extract_metadata_video_scene`
- `judge_narrative_arc` (Tier-L Opus, single call per job — N-001)
- `parse_user_brief`
- `recommend_effort_level`
- `explain_cost`, `explain_upgrade_path`
- `stream_chat`

All are `idempotency_class = free` (read operations from the orchestrator's perspective; the LLM API call itself has cost-side-effect tracked via ADR-0015 telemetry, not idempotency-class).

#### Pipeline tools (ADR-0010 / ADR-0011)

- `ingest_media(media_paths)` — Stage 1 (project_mutating)
- `compute_perceptual_hashes(content_hashes)` — Stage 1 (project_mutating)
- `segment_video_scenes(content_hashes)` — Stage 1 (project_mutating)
- `compute_dedup_clusters(content_hashes)` — Stage 1 helper (project_mutating)
- `pre_filter_candidates(brief, target_duration, overrides)` — Stage 4 (project_mutating)
- `compile_render_plan(arc_judgment, music_spec)` — Stage 6 (project_mutating)
- `orchestrator_second_guess(arc_judgment, render_plan)` — Stage 6 (free; LLM call)
- `execute_render(plan)` — Stage 7 (project_mutating)

#### Refinement tools (ADR-0011 Stage 9 / N-009)

- `re_run_stage_5_with_addendum(addendum)` — partial fix (project_mutating)
- `re_extract_metadata_for(items)` — partial fix (project_mutating)
- `re_run_pre_filter_with_overrides(overrides)` — partial fix (project_mutating)
- `request_user_input(prompt, options)` — pause + wait for user (free)
- `explain_why_not_possible(reason)` — terminal "give up" (free)

#### Music tools (ADR-0012)

- `analyze_music(audio_path)` — produce `MusicAnalysis` (project_mutating; cached)
- `analyze_music_duration_mismatch(music, target_duration)` — pick `DurationStrategy` (free; LLM call)

#### Connector tools (ADR-0013)

- `validate_publish_artifact(snapshot_id, platform, metadata)` — pre-flight check (free)
- `upload_to_platform(snapshot_id, platform, metadata)` — **external_side_effect** — requires explicit user Approve click
- `record_audit_event(audit_entry)` — append to audit log (project_mutating)

#### Person-library tools (ADR-0010 / N-008)

- `add_person(display_name, notes)` — (project_mutating)
- `add_face_photo(person_id, content_hash, face_crop_bbox)` — (project_mutating)
- `build_reference_collage()` — refresh the cached collage (free; cached)
- `remove_person(person_id, confirm)` — (project_mutating; cache invalidation cascades)

#### Profile tools (this ADR / N-010 — new)

See "Cross-project user profile" section below.

- `read_user_profile()` — (free)
- `suggest_from_profile(stage, context)` — context-aware profile-derived suggestion (free; LLM call to compose the suggestion text)
- `record_feedback_event(event_type, payload)` — append to feedback log (project_mutating cross-project)
- `derive_profile_priors()` — re-derive priors from feedback log (free; LLM call; runs at job-end + on-demand)

### Reasoning model

Tool-call loop. The orchestrator's prompt template assembles:

1. The current job's state (project, brief, target_duration, mode, music spec, current snapshot's `plan.json`, latest `ArcJudgment`, latest `SecondGuessResult`).
2. Available tools (filtered by current pipeline stage; tool descriptions + input schemas).
3. **Profile context** (relevant slices of the user profile — see below).
4. The user's most recent input (refinement message, brief, etc.).

The orchestrator picks one tool per turn, executes, observes the result, decides next step. **Bounded at 50 tool calls per orchestration session.** The refinement subloop (ADR-0011 Stage 9) has its own 10-turn bound on top.

Beyond 50 turns: pause job, persist state, surface "we hit the iteration limit" via the failure-mode UX (below).

### Cross-project user profile (N-010)

The orchestrator's persistent memory across projects. Per Q4: "build a user profile over time which can help the impact crater suggest ideas to the user itself during new project creations, or also help impact crater to learn from its mistakes the next time around."

#### Storage location

`~/.impact-crater/profile/profile.json` (single file, atomically rewritten by the profile writer). For larger structured data, `~/.impact-crater/profile/feedback_log.jsonl` (append-only, growth-bounded by rotation policy in ADR-0015).

This is per-user (per OS user account); no cross-user sharing at MVP. v3 hosted-service mode (per CLAUDE.md mission) makes per-tenant profiles when it lands.

#### Schema (v1)

```python
class UserProfile(BaseModel):
    schema_version: int = 1
    created: datetime
    updated: datetime

    # Inferred from approve/refine patterns + brief parses + project metadata
    style_preferences: StylePreferences

    # The orchestrator's priors over its own decisions
    orchestrator_priors: OrchestratorPriors

    # Common narrative shapes the user gravitates toward
    narrative_patterns: NarrativePatterns

    # Pointer to the feedback log (single-source-of-truth for re-derivation)
    feedback_log_path: Path
    feedback_log_event_count: int           # for change-detection on re-derivation triggers


class StylePreferences(BaseModel):
    preferred_target_durations_seconds: list[int]      # observed list with frequency weights
    preferred_modes: dict[Literal["standard", "music_video"], float]   # frequency
    preferred_music_tempo_bands: dict[Literal["slow", "moderate", "fast"], float]
    preferred_pacing: dict[Literal["slow_cuts", "moderate", "fast_cuts"], float]
    common_brief_motifs: list[str]                     # extracted phrases ("family vacation", "summit attempt", etc.)
    bias_toward_landscape_vs_people: float | None      # -1 (people-heavy) to +1 (landscape-heavy)


class OrchestratorPriors(BaseModel):
    second_guess_acceptance_rate_by_type: dict[Literal["drop_item", "reorder", "shorten", "lengthen", "swap"], float]
    refinement_strategy_success_rate: dict[Literal["partial_fix_via_plan_edit", "partial_fix_via_stage_3_rerun", "full_reprocess"], float]
    pre_filter_override_acceptance_rate: float
    typical_quality_floor_override: float | None        # if user consistently raises/lowers the default 0.4 quality floor


class NarrativePatterns(BaseModel):
    common_arc_shapes: list[str]                        # "build_up_then_climax", "chronological", "energy_pulses", etc.
    preferred_openers: list[str]                        # role-tagged candidate descriptions
    preferred_closers: list[str]
    music_section_to_media_recurring_mappings: dict[str, str]   # if user often maps "chorus" → "summit shots"
```

#### Feedback log

Append-only JSONL. Each event:

```python
class FeedbackEvent(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    project_id: str                     # so we can scope or globally aggregate
    snapshot_id: str | None             # if event is snapshot-bound
    event_type: Literal[
        "approve",                       # user clicked Approve at preview
        "refine",                        # user clicked Refine at preview
        "second_guess_accepted",        # user accepted an orchestrator override
        "second_guess_rejected",        # user rejected an orchestrator override
        "second_guess_modified",        # user modified an orchestrator override
        "refinement_succeeded",         # refinement loop produced a render the user approved
        "refinement_failed",            # refinement loop hit explain_why_not_possible
        "pre_filter_overridden",        # user changed Stage 4 candidate count
        "effort_level_overridden",      # user changed effort level mid-job
        "publish_succeeded",            # connector reported success
        "publish_failed",                # connector reported failure
        "job_cancelled",                 # user cancelled mid-job
    ]
    payload: dict                       # event-type-specific structured details
```

The feedback log is the single source of truth. The `UserProfile` is **derived** from the feedback log; re-derivation is idempotent and can be run anytime.

#### Profile writer

Triggered on:

- **Job-end** (Stage 7 render complete OR Stage 9 refinement terminal): re-derive profile priors from the recent feedback events.
- **User feedback events** (approve/refine/second-guess decision): append to feedback log immediately; defer profile re-derivation to the next batch trigger.
- **Manual** ("re-learn from my history"): user-triggered from settings; full re-derivation from the entire feedback log.

Re-derivation uses a Tier-M LLM call (`derive_profile_priors`) that reads the recent feedback events + the current profile and produces an updated profile. The LLM is prompted to reason structurally (frequency weights, success rates, motif extraction) rather than free-form summarize.

Re-derivation is bounded by event-count: after every N=10 new feedback events (configurable), re-derive incrementally. After every N=100, full re-derivation from the log (more compute; corrects drift).

#### Profile reader (call sites)

- **Job creation:** the FastAPI new-project handler reads the profile and surfaces suggestions to the user — "Based on your past trips, you usually want ~90s videos with energetic music; pre-fill these?" The user can accept, modify, or ignore. UI surface = pre-filled form values + an "i" tooltip explaining the inference.
- **Brief parsing (Stage 5 prep):** the `parse_user_brief` call template includes profile motifs as in-context priors (e.g., "this user often briefs about family events; consider that when extracting structure").
- **Pre-filter (Stage 4):** profile-derived `typical_quality_floor_override` (if non-null) replaces the hard-coded 0.4 default.
- **Narrative-arc judgment (Stage 5):** profile narrative patterns are passed to the Tier-L Opus call as structured context ("this user gravitates toward `build_up_then_climax` arcs and prefers slow-cut pacing").
- **Orchestrator second-guess (Stage 6):** the orchestrator's confidence threshold for surfacing overrides shifts based on `second_guess_acceptance_rate_by_type` — high-acceptance override types surface at lower confidence; low-acceptance types only surface above a higher threshold.
- **Refinement (Stage 9, N-009):** the orchestrator's strategy choice in the thinking step is biased by `refinement_strategy_success_rate` — strategies that historically worked for this user get higher prior weight.

#### Privacy posture

- **The profile and feedback log live entirely on disk.** They never leave the machine except as in-context priors inside Tier-M LLM calls (the same calls the orchestrator already makes). No telemetry uploads. No cross-user sharing.
- **The profile is small enough to fit in a Sonnet-class context window** (typically <50 KB serialized). The full profile is never loaded into the Opus narrative-judgment call (Stage 5) — only relevant slices are passed.
- **User can reset the profile** ("forget what you've learned about me") via settings. Resets the feedback log + profile.json to empty; subsequent projects start fresh.
- **Person-library data (N-008) does not flow into the profile.** Faces stay in the person library SQLite tables (per ADR-0006); the profile sees only abstracted patterns (e.g., `bias_toward_landscape_vs_people`) derived from candidate-set composition, not identities.
- **Cross-project content-hash references in the feedback log** allow tracing a feedback event back to the specific media. This is intentional for the audit trail; users who want stricter isolation can use the reset-profile path.

#### Why this is novel (N-010)

See [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md) → N-010. Briefly: most AI-driven creator tools treat each session as stateless. The agentic learning loop where the orchestrator's own decisions are tracked, rated by user response, and converted into priors that influence future decisions — applied to the per-stage tool-call loop of a media curation pipeline — is fresh.

### Failure-mode UX (per Q3)

When the orchestrator gets stuck (max-tool-call-bound; repeated failures; contradictory state), it pauses the job, persists current state, and surfaces a "we got stuck" message via the FastAPI websocket. The UI presents three actions:

- **Continue** — user provides additional context ("look at day 3 photos specifically"); the orchestrator's tool-call loop resumes with the new context (the 50-turn budget is reset per "continue" click).
- **Abandon** — mark the snapshot as `failed`; the user can start a new render or reuse the previous good snapshot.
- **Restart** — start fresh from the current job state at Stage 4 (pre-filter); useful when the orchestrator went down a wrong path early.

**Manual override** (user directly edits `plan.json`) is **v1**, not MVP. Power-user feature; needs UI design + safety rails to be useful.

The "stuck" message includes:

- A summary of what the orchestrator was trying to do.
- The last few tool-call attempts + their results.
- Any orchestrator-recognized contradictions in the state.
- Cost spent so far (per ADR-0015 telemetry).

### Cancellation

User can cancel any orchestration session via the in-progress UI's Cancel button. Cancellation:

- Sets a `JobCancelled` flag on the job state.
- The orchestrator checks the flag between tool calls; if set, raises `JobCancelled`.
- In-flight tool calls (e.g., an in-progress ffmpeg subprocess) honor cancellation per ADR-0010 worker pool: SIGTERM with grace period then SIGKILL.
- Current snapshot persists with status `cancelled`; the user can resume from this snapshot later.

### Resume after crash

- On startup, the FastAPI process scans for snapshots with status `in_progress` (any job that didn't reach a terminal state).
- For each, surface "Resume?" prompt to the user via the dashboard.
- On resume: orchestrator reads `plan.json` + cache state + feedback events since last save and continues the tool-call loop.

## Alternatives considered

- **No chat-memory beyond the current tool-call loop (the original proposal).** Stateless per-project; matches D-017's bare-minimum interpretation. Rejected per Q4 — user wants cross-project learning. The cross-project profile is meaningfully more product than the stateless version, at the cost of additional persistence + LLM calls (the per-job profile re-derivation).
- **Multi-agent harness at MVP.** Rejected per D-017 — flexibility we don't need yet; multi-agent → v2.
- **Model-fine-tuning instead of profile-based priors.** Considered for the "learning from mistakes" half. Rejected — fine-tuning a Tier-M model per user is expensive, requires infra we don't have, and updates would lag behind feedback events. Profile-based priors via in-context conditioning are immediate and cheap.
- **Per-project-only learning (no cross-project).** Half-step option: still useful for refinement loops within a project. Rejected per Q4 — the cross-project value is exactly the differentiator.
- **Manual override at MVP.** Rejected per Q3 — three actions are sufficient; manual override needs UI design + safety rails not worth building at MVP.
- **Profile derivation via deterministic rules (no LLM).** Rejected — the motif extraction + narrative-pattern detection benefit from LLM understanding; deterministic frequency-counting alone is too shallow.
- **Profile in SQLite instead of JSON file.** Considered. JSON file is simpler for a small (<50 KB) document that's read whole and atomically rewritten; SQLite would add transaction overhead for marginal benefit. Feedback log uses JSONL (append-only) for the same simplicity reasons.

## Consequences

- **The orchestrator is no longer stateless across projects.** A user's third project benefits from learnings from their first two. This is the differentiator vs every other AI media-curation product.
- **Profile re-derivation adds Tier-M calls per job-end** (~$0.005 per call; see ADR-0009 cost envelope). Negligible vs the per-job total.
- **The feedback log grows over time.** Rotation policy (e.g., archive events older than 6 months; full re-derivation on rotation) is part of ADR-0015's telemetry-rotation story.
- **Profile reset is a one-click feature.** Users who want a fresh start can wipe the profile + feedback log without affecting projects, snapshots, or person libraries.
- **The profile schema (v1 here) is the contract for v1's profile-driven UX.** v1 will likely add: per-project temporary profile overrides, project-tagged feedback (so different project types — vacation vs build — derive different priors), and an explicit "what you've learned" UI surface.
- **The 50-turn orchestration bound is conservative.** Most jobs complete in 10–30 turns. The bound exists to prevent infinite-loop pathologies, not to limit productive work. If MVP testing shows real jobs hitting the bound, raise it.
- **Multi-user / multi-tenant (v3 hosted-service)** requires per-tenant profile storage. The schema transfers; the path becomes `{tenant_id}/profile.json`. ADR-0006's storage abstraction already anticipates this.
- **The "external_side_effect" idempotency class** ensures publish-style tool calls always require explicit user confirmation. The orchestrator can plan to publish; it cannot publish without the user clicking through.

## Linked items

- D-017 (single orchestrator harness — formalized here), D-013 (effort levels — orchestrator surfaces recommendation; profile may bias the default), D-022 (refine offered post-render), A-005 (failure recovery — resume-from-snapshot path here), A-015 (cost-transparency UI — surfaces failure-mode messages and profile-derivation costs).
- ADR-0005 (FastAPI process — orchestrator lives here), ADR-0006 (snapshot persistence + profile path), ADR-0007 (LLM operations the orchestrator calls), ADR-0009 (per-operation cost tier), ADR-0010 (pipeline tools), ADR-0011 (Stage-by-Stage tool sequence; second-guess at Stage 6), ADR-0012 (music tools), ADR-0013 (connector tools).
- Cascades to: ADR-0015 (orchestrator-turn-event telemetry; profile-derivation cost surfaced; feedback-log rotation policy lives there), ADR-0016 (privacy posture for what flows into the profile).
- Novel mechanism: **N-010** (cross-project user profile + agentic learning loop) — see [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md). References **N-009** (the refinement loop's strategy choice now reads profile priors).
- Decision-log entry: D-033 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.3.2 in [`project/tasks/`](../../project/tasks/T-1.3.3.2-adr-0014-agent-harness.md).
