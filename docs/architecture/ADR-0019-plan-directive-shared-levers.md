# ADR-0019 — PlanDirective: shared duration/positional/tempo shaping levers

Status: accepted
Date: 2026-06-30
Supersedes: none
Related: ADR-0011 (render pipeline), ADR-0014 (agent harness / refinement), ADR-0017 (brief-driven coverage), E-2.12

## Context

Stage 6 (`compile_plan`) shapes clip durations with **hard-coded module
constants** (`_PHOTO_MIN_MS=1000`, `_PHOTO_MAX_MS=3000`, `_VIDEO_MIN_MS=2000`,
`_MAX_CLIPS_PER_LOCATION=3`, montage bands). The second-guess pass and the M6
refinement (`stage9_refine`) can only re-run the judge with a brief addendum —
`apply_overrides` logs and skips `shorten`/`lengthen`. So there is **no way to
express** the kinds of pacing edits users ask for:

- "make the clips in the beginning 50% longer / 2s longer, and reduce the
  photos around them by 0.5s" (positional emphasis)
- "increase photo duration/frequency with the song's rising tempo in the later
  half, decrease with falling tempo" (tempo-aware pacing)
- "soft-align cuts to the music's sections in standard mode" (S-2.11.6, the
  optional lever that was deferred)

These are all *duration/positional/tempo shaping* — a concern separate from
*which media appears* (Stage 4/5). They should be one contract used by both the
initial plan and the refinement layer, so an initial render and a refined
re-render run **identical Stage-6 code**.

## Decision

Introduce **`PlanDirective`** (`backend/impact_crater/pipeline/plan_directive.py`)
as the single duration/positional/tempo shaping contract that Stage 6 consumes
and the refinement layer emits.

- `PlanDirective(bands, max_clips_per_location, positional_rules, tempo,
  soft_align, provenance)`. `DEFAULT_DIRECTIVE` reproduces today's constants
  **exactly** (a no-op), so existing renders and tests are byte-identical until
  a lever is populated.
- Three levers, all read from one directive:
  - **positional** — per-region (timeline fraction 0..1) duration multipliers +
    ms deltas, with a neighbour shoulder ("make the opener longer AND shrink the
    photos around it" is one rule);
  - **tempo** — ordered `TempoBand`s (song halves or sections) with duration and
    density multipliers derived from `music.energy_curve` / section tempo;
  - **soft_align** — in standard mode only, nudge cumulative clip boundaries onto
    section starts within a window (S-2.11.6; never reorders/drops).
- Stage-6 applies levers in a **fixed order** (standard mode): montage-collapse
  → `_cap_per_location` (from `directive.max_clips_per_location`) → positional →
  tempo → `_scale_to_target` (directive-aware bands) → optional soft-align.
- `RenderPlan.directive` is **persisted on plan.json** (schema_version bump;
  `load_plan` tolerates old plans via a default). It is the merge base for the
  next refinement, so successive refinements compound.
- **Refinement** (`stage9_refine`) emits a **partial** `PlanDirective`;
  `merge_directive(base, patch)` deep-merges it over the persisted base and
  re-runs `compile_plan` **only** (same `arc_judgment`, no new Opus judge) for
  pure pacing edits. This is what finally makes `shorten`/`lengthen` real.
- **Music-video mode is unchanged**: the hard beat-snap owns pacing;
  `directive.soft_align` is ignored there.

The directive application is deterministic; it is *AI-influenced* only through
the refinement/second-guess tool that emits the partial directive.

## Consequences

- One shaping contract for initial planning and refinement — no divergent code
  paths, no hand-editing of clip durations in the refinement layer.
- `apply_overrides`/second-guess `shorten`/`lengthen` can converge onto the same
  `directive_patch` mechanism (follow-on task).
- `RenderPlan` schema changes; the additive default keeps old plans loadable.
- Density shaping (`tempo.apply_density`) changes *which/how-many* clips show and
  collides with Stage-4/5 selection + coverage guarantees, so the first cut
  ships **duration-only** tempo shaping (`apply_density=False`); density is a
  gated follow-on.
- `directive.max_clips_per_location` must equal or be a strict secondary guard
  to the Stage-4 `_cap_gps_viewpoints` (T-2.11.1.6) — one layer owns the number,
  never a third independent cap.
