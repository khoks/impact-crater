# ADR-0021 — Deterministic stage runner with single-shot structured LLM calls

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-10-25
**Phase:** mvp-hardening (restart Phase 0, S-2.13.5)
**Supersedes:** the harness sections of [ADR-0014](./ADR-0014-agent-harness-topology.md) — *Topology*, *Tool registry*, *Consolidated tool surface*, *Reasoning model*, *Failure-mode UX*, *Cancellation* and *Resume after crash*. ADR-0014's *Cross-project user profile (N-010)* section is **not** superseded; it stands as a design whose backend and endpoints exist without emitters or UI (see `ARCHITECTURE.md` → Amendments).

## Context

D-017 (2026-04-27) fixed the MVP harness as "a single orchestrator with structured tool calls", and ADR-0014 (2026-05-03) specified it in detail: an `Orchestrator` class on Tier-M, a tool registry with `idempotency_class`, a 50-turn tool-call loop, a 10-turn refinement subloop (N-009), continue / abandon / restart failure UX, cancellation through the loop, and a startup scan that offers to resume `in_progress` snapshots.

None of that was built. What shipped between M1 (2026-05-04) and E-2.12 (2026-07-01), and what passed the curate→preview half of the D-014 gate on 2026-06-18 on a real 1,663-asset trip, is a **deterministic runner**: `backend/impact_crater/pipeline/runner.py` sequences the stages in fixed code and every AI step is **one** structured call. The 2026-10-24 restart audit (`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md` §4.3 C items 12 and 18) asked for the shipped shape to be recorded as the decision, the never-built loop to be formally deferred, and the orphaned plumbing to be deleted. Verified against master `d9bb392` on 2026-10-25.

## Decision

### 1. The harness is the deterministic runner

`run_headless_pipeline` runs Stages 1–5; `run_full_pipeline` runs the whole job. Stage order as it runs today (the numbering keeps ADR-0011's spine; the half-numbered stages were inserted later):

| Stage | Module | Kind | Notes |
|---|---|---|---|
| 1 Ingest | `pipeline/stage1_ingest.py` | deterministic + ffmpeg/ffprobe | content hashes, pHash, scene segmentation, renditions, sidecars |
| 2 Bulk ops | `pipeline/stage2_bulk_ops.py` | Tier-S + embedding | `caption_image`, `score_image`, `embed_image` (caption-then-embed, ADR-0018 pending) |
| 3 Metadata | `pipeline/stage3_metadata.py` | Tier-M | `extract_metadata_image` for photos **and** scene frames (one router op; the video-scene schema is passed as the tool schema) |
| 3.5 Trip cast | `pipeline/cast_builder.py` | deterministic (+ face embeddings) | A-018 / N-012, fail-soft |
| 0.5 Brief intent | `pipeline/brief_intent.py` | Tier-M (`parse_user_brief`) | ADR-0017, cached, fail-soft |
| 4 Pre-filter | `pipeline/stage4_prefilter.py` | deterministic | quality floor, dedup, caps, `ReservationSet` must-keeps (S-2.10.5) |
| 5 Judge | `pipeline/stage5_judge.py` | Tier-L | `judge_narrative_arc`, one forced-tool call per job |
| 0 Music analysis | `media/music.py` (`LibrosaMusicAnalyzer`) + `generate_cut_grid` | deterministic (librosa) | runs at the start of `run_full_pipeline` when audio is supplied; fail-soft; recomputed every job (no cache) |
| 6 Plan | `pipeline/stage6_plan.py` | deterministic | `PlanDirective` (ADR-0019), music grid, montage |
| 6.5 Second-guess | `pipeline/stage6_second_guess.py` | Tier-M (`parse_user_brief`) | fail-soft; applied internally, no user reconfirm |
| 6.x Title card | `pipeline/stage6_title_card.py` | Tier-S text + optional image | opt-in |
| 7 Render | `pipeline/stage7_render.py` | ffmpeg | 16:9 1080p |
| 9 Refine | `pipeline/stage9_refine.py` | Tier-M (`parse_user_brief`) + re-run of 6 or 4→5→6 | see §2 |

Progress reaches the UI through `jobs/registry.py::JobRegistry` and the WebSocket `/api/jobs/ws/{job_id}` (`api/jobs.py`), not through orchestrator turns. Telemetry ties a job's events together with one `correlation_id` per job (plus `refine-{snapshot_id}` for refinements).

**Single-shot structured calls.** Each AI step is one call through `llm_clients/router.py::LLMRouter`: Anthropic ops force a single tool whose `input_schema` is the expected JSON Schema (`_call_tool_use`); Google ops use prompted JSON (`_call_with_schema`). The router owns caching, rate-card pricing, telemetry and quota recording. Nine operations are routed in `config/llm-routing.yaml` after S-2.13.7: `embed_image`, `embed_text`, `caption_image`, `score_image`, `generate_title_text`, `extract_metadata_image`, `parse_user_brief`, `generate_title_background`, `judge_narrative_arc`. Every routed operation has a `LLMRouter` method; every operation with a `prompts/<op>/` directory has a template for its routed model (`tests/test_routing_config_integrity.py`).

### 2. N-009 is realised as the single-call refinement planner (D-056)

ADR-0011 Stage 9 and N-009 described a Tier-M "thinking step" that picks one of five strategies inside a bounded 10-turn tool loop. What shipped (E-2.12, PRs #72 / #73, D-056) keeps the *idea* — the AI decides **how** to refine, climbing back only as far up the pipeline as the request needs — and realises it as **one** structured call: `stage9_refine.plan_refinement` renders a richly contextualised prompt (brief, clip-by-clip plan, named destinations, music, the request, a description of the levers) and gets a `RefinementOutcome` back. Its levers are the two shared curation contracts: a `directive_patch` (`PlanDirective`, ADR-0019 — pacing only, re-runs **Stage 6**), `reserve_destinations` / `reserve_refs` (`ReservationSet` — re-runs **Stage 4 → 5 → 6**), a `brief_addendum` (re-judge), a `title_card_patch`, or an `explanation` when the request cannot be honoured with this media. `execute_refinement` rebuilds the context from the `sources/*.json` sidecars and the LLM cache (no re-ingest) and renders a **child snapshot**. The full code-level trace is `PIPELINE_DATAFLOW.md` → Stage 9.

The cost-aware strategy choice, the "give up and explain" outcome and the per-snapshot persistence of the chosen plan (`refinement_plan.json`) from N-009 all exist; the multi-turn loop, `request_user_input` and the Stage 3 re-extraction strategy do not. Refinement runs synchronously inside `POST /api/snapshots/{id}/refine` (S-3.5.5 makes it a job).

### 3. The agentic loop is deferred, not cancelled

- Multi-agent harness (planner + media-analyst + editor + publisher) → **E-4.2** (v2), as D-017 already said.
- Multi-turn conversational refinement with profile-derived priors → **E-4.3** (v2).
- Reopening either needs evidence from the E-3.10 eval harness that a class of real requests cannot be honoured by one well-contextualised call. Until then the single-call pattern is the default for every new AI decision point (it is what the second-guess, the brief intent, the title text and the refinement planner all use).

### 4. Orphaned plumbing is deleted (S-2.13.7)

The never-called `LLMClient.tool_call` and `stream_chat` (both providers) and their `ToolSpec` / `Message` / `ToolCall` types, the never-emitted `telemetry.OrchestratorTurnEvent`, the `orchestrator_reasoning` route and its tier-lookup entry, the five other routed-but-unimplemented operations (`recommend_effort_level`, `explain_cost`, `explain_upgrade_path`, `caption_video_scene`, `extract_metadata_video_scene`), and the empty `api/ws.py` placeholder router. The `analyze_music_duration_mismatch` tool of ADR-0012 was never routed or built; the render trims and fades the music to the actual timeline (`stage7_render.py` Phase 3) and no fade / loop / truncate picker is scheduled.

### 5. What the runner does not do (recorded, with homes)

- **No resume after crash.** `JobRegistry` is in-memory; there is no `jobs` table and no startup scan. A server restart loses in-flight job state; snapshots on disk survive. → S-2.9.19 (restart Phase 2).
- **No mid-job quota check.** `quota.check_quota` runs once before Stage 1. → S-3.11.1.
- **No continue / abandon / restart UX.** A failed job is reported as failed; the user re-submits or refines the last good snapshot.
- **Refinement is not a job** (no progress stream, no cancel). → S-3.5.5.
- **Cancellation** exists at the worker-pool level (`workers.py`, SIGTERM then SIGKILL for ffmpeg) and the job level (`JobRegistry.cancel_job`), not as a per-turn check.

## Alternatives considered

- **Build the ADR-0014 `Orchestrator` loop as specified.** Rejected. The pipeline's branching points are few and known (keep / drop, re-judge or not, which lever), so a per-turn Tier-M call adds latency and spend (ADR-0009 budgeted ~80 turns per job) without adding decision value. The shipped shape passed the D-014 gate.
- **A hybrid where an agent chooses the stage order but each stage stays deterministic.** Rejected for the same reason; the stage order has never needed to vary.
- **Keep ADR-0014 as the decision and label the runner "interim".** Rejected: four months of real jobs ran on the runner, D-057 closes the MVP on it, and the public docs (OVERVIEW / README / ARCHITECTURE) already describe it. Architecture docs must describe what runs.

## Consequences

- ADR-0007's `LLMClient` protocol loses `tool_call` / `stream_chat`; its `params: dict` is the `CallParams` dataclass in code (see ADR-0007 Amendments).
- ADR-0009's routing table shrinks to the nine operations above and loses the "~80 orchestrator turns" line of the cost envelope (see ADR-0009 Amendments → current pins).
- ADR-0011 Stage 9 and N-009 are read through this ADR and D-056; `NOVEL_IDEAS.md` N-009 is left as the historical disclosure, with its realisation recorded here.
- ADR-0015 carries four event types, not five (`OrchestratorTurnEvent` removed).
- E-4.2 and E-4.3 are where the agentic ideas live; a future ADR reopens them with eval evidence.
- `CLAUDE.md` "Decisions locked" and `ARCHITECTURE.md` → Agent harness point here.

## Linked items

- Decisions: D-017 (single orchestrator — superseded in shape by this ADR), D-056 (two shared curation levers; single-call planner), D-057 (MVP closure on the shipped shape).
- Novel mechanisms: N-009 (realised as §2), N-010 (profile — design stands, unbuilt emitters).
- ADRs: ADR-0007, ADR-0009, ADR-0011, ADR-0014 (superseded in part), ADR-0015, ADR-0017, ADR-0019.
- Tracker: S-2.13.5 (this ADR), S-2.13.7 (deletions), S-2.9.19, S-3.11.1, S-3.5.5, E-2.12, E-3.10, E-4.2, E-4.3.
- Code-level trace: [`PIPELINE_DATAFLOW.md`](./PIPELINE_DATAFLOW.md).
