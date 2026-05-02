# ADR-0011 — Curation engine algorithm shape

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-02
**Phase:** scaffolding

## Context

D-009 fixed the high-level shape of the curation pipeline as a **hybrid: deterministic pre-filter → rich metadata extraction → narrative-arc judgment → render with music sync**. N-001 surfaced the **narrative-arc judgment stage** as the load-bearing novel mechanism. ADR-0007/0009 locked the LLM abstraction and the per-operation cost-tiered routing. ADR-0006 locked the snapshot-as-versioned-artifact substrate. ADR-0010 locked the deterministic media-pipeline floor. ADR-0011's job: nail down the actual algorithm — the 9 stages, their input/output schemas, the cache reuse story, and three user-redirected behaviors:

- **Stage 4 pre-filter is user-overridable with a floor + ceiling.** No silent reduction below a minimum candidate count; never select more than 80% of input as candidates (per Q5).
- **Stage 9 refine is agentic with custom plan generation** (filed as **N-009**, the novel mechanism). The user's NL refinement message kicks off a thinking step that chooses between full reprocess and partial fix based on context + tools available.
- **Stage 6 plan compilation can second-guess the N-001 judge but must reconfirm with the user before applying overrides** (per Q7).

## Decision

### The 9 stages

```
[1] Ingest + content-hash + scene-segment + thumbnails       (deterministic, ADR-0010)
        ↓
[2] Bulk per-asset operations: embed + caption + score       (Tier-S + embedding)
        ↓
[3] Rich metadata extraction (D-009 schema + recognized_persons via N-008)
                                                              (Tier-M)
        ↓
[4] Pre-filter: quality-floor + dedup-grouping +
    location/time clustering → candidate set                  (deterministic)
        ↓
[5] Narrative-arc judgment (N-001)                            (Tier-L Opus)
        ↓
[6] Plan compilation + orchestrator second-guess +
    music alignment (ADR-0012)                                (deterministic + Tier-M)
        ↓
[7] Render                                                    (deterministic, ffmpeg)
        ↓
[8] Preview UI with twin Approve / Refine                     (UI; D-022)
        ↓
[9] Agentic refinement (optional; N-009)                      (Tier-M tool-call loop)
```

### Stage 1 — Ingest + content-hash + scene-segment + thumbnails

Per ADR-0010. Outputs:

- `media` SQLite rows (one per source media, keyed by content hash).
- Source sidecars at `~/.impact-crater/projects/{project_id}/sources/{content_hash}.json` with quick stats.
- Thumbnails at the cache path.
- Per-video scene list at `~/.impact-crater/projects/{project_id}/cache/scenes/{content_hash}/scenes.json` with `(start, end, representative_frame_paths[3])` per scene.

### Stage 2 — Bulk per-asset operations

For each photo and each video scene, in parallel (worker-pool concurrency per ADR-0005 / ADR-0010):

- `embed_image` → embedding cached at `cache/{content_hash}/{provider}_{model}_{version}/embedding.npy`.
- `caption_image` → 1-line caption cached as `caption.txt`.
- `score_image` (quality dimension) → quality score cached as `score-quality.json`.
- `score_image` (narrative-value dimension, brief-aware) → narrative-relevance score cached as `score-narrative-{brief_hash}.json`. **Brief-aware** because the same image scores differently against different briefs ("family vacation" vs "summit attempt").

For video scenes, the same operations run on the scene's representative frames; the scene-level outputs are aggregated (e.g., scene caption = LLM-summarized aggregate of the 3 frame captions; the aggregation itself is a Tier-S call).

Cache reuse (per A-011, N-007): re-running curation on the same media against the same brief gets free Stage-2 hits except for `score_image (narrative-value)` if the brief changed; brief-aware scores re-run on brief change.

### Stage 3 — Rich metadata extraction

For each photo and each video scene, in parallel (rate-limited per the routing config):

- `extract_metadata_image` (or `extract_metadata_video_scene`) → returns the D-009 rich schema:
  - `time_of_day`, `people` (count + age bands + recognition results from N-008 if library non-empty), `lat_long`, `location_description`, `mood`, `lighting`, `quality`, `foreground_activity`, `background_activity`, `objects` (S/M/L size buckets), `clothing`, `pose_quality_scores`, `generic_tags`, `task_context_tags` (brief-aware).
- Schema-validated structured output (per ADR-0007). Schema-mismatch → retry once → raise `LLMOperationFailed`.
- Cache: keyed by content-hash + provider + model + model_version + prompt_version + (when person-library is non-empty) `library_version_hash`.

### Stage 4 — Pre-filter

**Deterministic, no LLM.** Inputs: full media set with Stage-2 + Stage-3 outputs. Output: a **candidate set** sized between a floor and a ceiling.

**Floor and ceiling math:**

```
floor   = max(50, ceil(target_duration_seconds × 2))
ceiling = floor(input_count × 0.80)
target_size = clamp(default_target, floor, ceiling)
default_target = max(floor, min(ceiling, ceil(input_count × 0.30)))
```

- **Floor = max(50, target_duration × 2).** Floor of 50 candidates so the narrative-arc judge always has a real working set; floor of 2 candidates per second of target so a long-target Story Video doesn't get starved.
- **Ceiling = 80% of input.** Per Q5; never claim "we curated" when nearly everything is included.
- **Default target = ~30% of input.** Reasonable default per Q5; clamped into the floor / ceiling envelope.
- **Edge case: input < floor.** If the user uploads only 30 photos, the floor pulls candidate-set size up to 30 and pre-filter is effectively a pass-through. This is correct — there's nothing to filter.
- **User overrides** (per Q5): the user can adjust `target_size` via the effort-level UX (D-013), within the `[floor, ceiling]` envelope. Going below floor or above ceiling is **not allowed** even by the user — the math is hard-capped. Going outside the envelope requires a different UX (e.g., uploading more media to lower the floor pressure, or shortening target_duration).

**The pre-filter logic itself:**

1. Apply quality floor: drop items where `quality_score < threshold` (default 0.4 on a 0–1 scale; configurable). Floor applies before clustering so we don't waste cluster slots on technical garbage.
2. Compute dedup clusters via Stage-2 perceptual hashes (Hamming ≤ 5 on pHash). Each cluster contributes at most ⌈cluster_size / dedup_factor⌉ items to the candidate set; default dedup_factor = 3.
3. Compute time + location clusters from EXIF + GPS. Clusters of >10 items get down-sampled to 10 (representative members chosen by quality + narrative-relevance).
4. Within remaining set, rank by `combined_score = α × quality + β × narrative_relevance + γ × scene_diversity`. Default α=0.3, β=0.5, γ=0.2.
5. Take top `target_size` items.
6. Output: `CandidateSet{ items: list[CandidateRef], cluster_metadata: dict, filter_log: list }`.

The `filter_log` records why each item made or missed the cut; surfaced in the cost-transparency UI (A-015) so users can see "we dropped 47 photos due to quality floor; 12 due to dedup."

### Stage 5 — Narrative-arc judgment (N-001)

**One Tier-L Opus call per job.** Inputs: the `CandidateSet`, the user's parsed brief, target_duration, music spec (from ADR-0012), mode (standard / music-video), the user's optional section-to-media NL mapping (per A-013 — pulled into MVP per Q10).

The prompt assembles:

- A condensed metadata summary per candidate (caption + 6-8 most-discriminative metadata fields, not the full rich schema — keeps the context window manageable).
- The brief verbatim.
- Target_duration + mode.
- For music-video mode: the music's beat grid + section structure + the user's section-to-media NL mapping.
- (Optional) For refine pass: the parent `ArcJudgment` + the user's refinement message.

Output: `ArcJudgment` structured as:

```python
class ArcJudgment(BaseModel):
    selected_items: list[SelectedItem]   # ordered, with placement metadata
    arc_reasoning: str                    # the LLM's narrative explanation
    section_mapping: dict[str, list[int]] | None  # for music-video mode: section name → selected_item indices
    confidence: float
    open_questions: list[str]            # e.g., "no clear ending shot — consider including #47?"

class SelectedItem(BaseModel):
    candidate_ref: str                   # content-hash + (scene index for videos)
    placement_position: int              # ordinal in the timeline
    intended_duration_ms: int            # how long this clip plays (estimated; final pinned in Stage 6)
    role: Literal["opener", "scene_set", "peak", "callback", "closer", ...]
    notes: str                           # the LLM's per-pick rationale
```

This is the **load-bearing N-001 mechanism**: the LLM-as-narrative-judge over the candidate set, producing a structurally-typed plan with reasoning. The structured output makes downstream stages deterministic.

Cache: keyed by `sha256(candidate_set_hash + brief + target_duration + music_spec + mode + section_mapping)`. Reuse on a re-run with the same inputs is automatic; the refine pass does *not* hit this cache because the refinement message changes the input.

### Stage 6 — Plan compilation + orchestrator second-guess + music alignment

**Deterministic + Tier-M (orchestrator second-guess).** Inputs: `ArcJudgment`, music structure (from ADR-0012). Output: `RenderPlan` persisted at `snapshots/{snapshot_id}/plan.json` (per ADR-0006).

The plan compiler:

1. Walks the `selected_items` in order, snapping each to the music beat grid (ADR-0012) for music-video mode.
2. Computes final clip durations (intended → snapped to nearest beat for music-video mode; respected as-is for standard mode).
3. Inserts transitions: simple cuts by default; cross-fades on slow-tempo music; quick cuts on high-energy sections.
4. Validates total duration against `target_duration`; if mismatch, applies the agentic-music-duration-handling per ADR-0012.
5. Validates aspect ratios; runs smart-crop where needed (ADR-0010).
6. **Orchestrator second-guess pass** (per Q7):

#### Orchestrator second-guess flow

After the plan compiler produces a draft `RenderPlan`, the orchestrator runs a **sanity-check pass** with the goals:

- Catch obvious duplication the judge let through (e.g., 3 near-identical sunset shots in the timeline).
- Catch obvious gaps (e.g., a 90-second target with only 12 selected items averaging 7.5 sec each — too slow).
- Catch obvious narrative problems (e.g., the "closer" item is timestamped before half the "scene_set" items in the source media).

This sanity-check uses a Tier-M (Sonnet) call: **`orchestrator_second_guess(ArcJudgment, RenderPlan, music_spec, brief) → SecondGuessResult`**.

```python
class SecondGuessResult(BaseModel):
    overrides: list[Override]          # proposed changes to the plan
    overall_confidence: float           # 0..1; how confident the orchestrator is in its overrides
    rationale: str                      # explanation surfaced to user

class Override(BaseModel):
    type: Literal["drop_item", "reorder", "shorten", "lengthen", "swap"]
    target_position: int
    proposed_change: dict
    why: str
```

If `overrides` is non-empty AND `overall_confidence > 0.6`:

1. Pause Stage 6.
2. Surface the proposed overrides to the user via the in-progress UI (websocket per ADR-0005): **"The orchestrator suggests these changes to the plan. Apply, modify, or skip?"**
3. User chooses per-override: Apply / Skip / Modify-with-NL.
4. The chosen overrides apply; the plan is finalized.
5. User's choices persist on the snapshot (for audit + future learning).

If `overrides` is empty OR confidence is low, Stage 6 proceeds to the final plan without user intervention.

This is the **"second-guess but reconfirm with user"** behavior per Q7. It prevents the orchestrator from silently overriding the judge while still letting it catch real issues.

### Stage 7 — Render

Per ADR-0010. Reads `plan.json`, executes ffmpeg subprocesses, writes `snapshots/{snapshot_id}/render.mp4`. Render-time alignment with music per ADR-0012.

### Stage 8 — Preview UI

Per D-020 + D-022. Twin Approve / Refine actions. Approve → Stage publishing (ADR-0013, round 3). Refine → Stage 9.

### Stage 9 — Agentic refinement (N-009)

**The novel mechanism.** When the user picks Refine and supplies a natural-language message, the orchestrator runs a **thinking step** that decides what to do, then executes the chosen plan.

```
User NL message: "more landscape, less faces"
        ↓
Orchestrator thinking step (Tier-M)
        ↓
[chooses one of:]
  (a) partial-fix-via-plan-edit → re-run Stage 5 with brief addendum
  (b) partial-fix-via-stage-3-rerun → re-extract metadata for items missed
  (c) full-reprocess → re-run from Stage 4
  (d) request-additional-input → ask the user for a different music file, etc.
  (e) explain-why-not-possible → some refinements aren't realizable with current media
```

The thinking step is implemented as a **single tool-call loop** (orchestrator_reasoning per ADR-0009 Tier-M). The orchestrator has access to:

- The current `ArcJudgment` + `RenderPlan` + `SecondGuessResult` history.
- The user's brief, the brief's parse, target_duration, mode, music spec.
- Stage-3 rich metadata for the entire input set (not just the candidate set — for "more landscape" it may want items the pre-filter dropped).
- The user's NL refinement message.
- Tools: `re_run_stage_5_with_addendum(addendum: str)`, `re_extract_metadata_for(items: list[content_hash])`, `re_run_pre_filter_with_overrides(overrides: dict)`, `request_user_input(prompt: str, options: list[str])`, `explain_why_not_possible(reason: str)`.

The orchestrator emits a `RefinementPlan` (the chosen action) which is persisted on the new snapshot. The new snapshot's `parent.txt` points at the previous snapshot per ADR-0006. Users can compare snapshots in the multi-version comparison UI when A-006 lands in v1.

The thinking step itself is logged so users can see the orchestrator's reasoning ("I chose partial-fix-via-plan-edit because the metadata already includes landscape tags; no re-extraction needed"). This is part of the cost-transparency UI (A-015).

**Refinement tool-call loop characteristics:**

- Bounded: max 10 turns. Beyond that, give up and surface the failure to the user.
- Cancelable: user can cancel mid-refinement.
- Idempotent: re-running the refinement on a saved `RefinementPlan` produces the same outcome (modulo LLM stochasticity, mitigated by temperature controls).
- Cache-friendly: most refinements hit Stage-2 / Stage-3 cache fully; Stage-5 is the new cost.

### Cache reuse story

| Stage | Cache class (per N-007) | Reuse on re-run | Reuse on refine |
|---|---|---|---|
| 1 (ingest) | Universal | Free | Free |
| 2 (bulk ops) | Model-versioned for caption/score-quality; brief-context for narrative-relevance | Free if media + models unchanged | Free (orchestrator may re-run narrative-relevance with refined brief) |
| 3 (metadata) | Model-versioned + library-versioned | Free if no model/library bump | Free if model + library unchanged |
| 4 (pre-filter) | Deterministic on Stage-2/3 outputs + brief | Free | Re-runs if orchestrator chose `re_run_pre_filter_with_overrides` |
| 5 (arc judgment) | Per-input hash | Free if all inputs unchanged | Always re-runs (refinement message changes input) |
| 6 (plan compile) | Deterministic on ArcJudgment + music | Free if Stage 5 cached | Always re-runs |
| 7 (render) | Deterministic on plan | Free if plan unchanged | Always re-runs (plan changed) |

A typical refinement re-runs Stages 5–7 plus optionally Stage 4 (cheap). The bulk cost (Stages 2 + 3) is reused. Cost envelope per refinement: ~$1–5 USD vs. $7–22 for a full job per ADR-0009.

## Alternatives considered

- **Skip Stage 4 pre-filter.** Pass full input to Stage 5. Rejected — at 1000 photos, the Tier-L narrative-judge call would either drown in irrelevant context or have to be split across many calls, losing arc coherence.
- **Skip orchestrator second-guess.** Trust the N-001 judge fully. Rejected per Q7 — small but valuable safety net for obvious failures the judge might let through.
- **Always second-guess silently (no user reconfirm).** Rejected per Q7 — silent overrides break the trust model; user must see what the orchestrator changed.
- **Refine pass = re-run Stage 5 with parent ArcJudgment (no thinking step).** The simpler "round-1 proposal" version. Rejected per Q6 — user wants the orchestrator to choose the right approach per refinement, not always-Stage-5.
- **Refine pass = full reprocess always.** Wastes Stage 2/3 cache work. Rejected.
- **Brief-aware narrative-relevance scoring as part of Stage 3 (rich metadata) instead of Stage 2.** Considered. Kept in Stage 2 because the brief is small + the score is a single float; Tier-S Flash handles it cheaply. Stage 3 stays focused on the rich-schema extraction.
- **Quality floor as a fixed threshold (no user override).** Considered. Made user-overridable via effort-level UX because "quality" is subjective and user-dependent — wedding photos vs. summit-attempt photos have different floors.
- **Stage 6 plan compilation done by an LLM (not deterministic).** Considered. Kept deterministic for predictability; the second-guess pass is the LLM's hook into Stage 6.

## Consequences

- **Stage 5 is the highest-cost LLM call per job (Tier-L Opus).** Cache hits matter; the cache key is wide enough to invalidate on real input changes but narrow enough to maximize reuse.
- **Stage 6's user-prompt for orchestrator overrides adds a UI surface.** A modal-or-inline panel during job processing where the user can review proposed changes before render. UI design lands post-round-3.
- **Stage 9 refinements are bounded at 10 turns.** Beyond that, the orchestrator gives up. In practice 2–4 turns suffice for most refinements; the bound exists to prevent infinite-loop behavior on contradictory user requests.
- **The refinement thinking step is itself an N-NNN-class novel mechanism (N-009).** Most curation systems implement refine-loops as either "re-run with new prompt" or "manual edit." The agentic plan-generation step that chooses the cheapest viable path is fresh.
- **The orchestrator's second-guess introduces a Tier-M call per job.** ~$0.005 per call; one per render. Small.
- **Brief-aware narrative-relevance scores invalidate on brief change.** This is correct — re-using "summit attempt"-relevance scores for a "family vacation" brief would be misleading.
- **Per-snapshot persistence of orchestrator override decisions** lets us learn (in v1) which overrides users tend to accept vs. skip, training a smarter second-guess pass over time. Out of scope for MVP.
- **The 9-stage shape is the canonical pipeline.** v1 additions (multi-version comparison A-006, quality-floor calibration A-007, reference-media style A-014) plug into specific stages without changing the shape: A-006 reads from the snapshot graph (ADR-0006); A-007 tunes Stage 4's quality floor; A-014 adds a Stage-2.5 style-fingerprint stage between bulk ops and rich metadata.

## Linked items

- D-009 (curation pipeline shape — this ADR is the formalization), D-011 (job model — async, resumable), D-013 (effort-level UX — Stage 4 user-override surface), D-014 (success criterion — wall-clock applies to this pipeline), D-016 (routing default — per-stage Tier assignments via ADR-0009), D-017 (orchestrator harness — Stage 6 second-guess + Stage 9 thinking step), D-022 (refine offered post-render alongside Approve), A-001 (project model), A-005 (failure recovery — pipeline resumes from snapshot), A-006 (multi-version comparison — reads snapshot graph), A-007 (quality floor — tunes Stage 4), A-011 (cross-job cache — Stage 2/3 reuse), A-013 (section-to-media NL mapping — Stage 5 input, **MVP scope per round 2 redirect**), A-014 (reference-media style learning — v1 plugs into Stage 2.5), A-015 (cost-transparency UI — filter_log + thinking-step log surfaced).
- ADR-0005 (Python process, worker pool), ADR-0006 (snapshot persistence + cache), ADR-0007 (LLM client protocol), ADR-0009 (per-stage tier assignments), ADR-0010 (pipeline-floor outputs).
- Cascades to: ADR-0012 (music alignment hooks into Stages 5/6), ADR-0014 (orchestrator harness — Stage 6 + Stage 9 tool-call shape), ADR-0015 (resource accounting — telemetry from each stage).
- Novel mechanism: **N-009** (agentic refinement with custom plan generation) — see [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md). Also references **N-001** (narrative-arc judgment, the load-bearing Stage-5 mechanism) and **N-008** (face recognition via reference collage, used in Stage 3).
- Decision-log entry: D-029 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.2.2 in [`project/tasks/`](../../project/tasks/T-1.3.2.2-adr-0011-curation-engine.md).
