# ADR-0020 — Cast cluster merge-pass + capture-day stratified Stage-4 budget

Status: accepted
Date: 2026-07-01
Related: ADR-0011 (pipeline), ADR-0017 (coverage/specialness), N-012 (cast), E-2.12

## Context

Two independent, deterministic curation additions surfaced from the SW-US-trip
feedback:

1. **Over-split cast clusters.** The greedy single-pass face clusterer
   (`_cluster_faces`) is order-dependent: one person's early off-angle crops can
   seed a second cluster, so the party member is split in two. Because the
   group/crowd split (N-012) keys on recurrence breadth, a split member can be
   wrongly demoted to *crowd* (under-counting the cast, skewing coverage).

2. **Later trip days starved.** Stage 4's final selection is a single global
   top-K by combined score. When the earliest day holds the sharpest shots, a
   long trip's later days can be squeezed out entirely — the same class of
   problem as the Vegas fix (S-2.10.5), but by *day* rather than named place.

## Decision

- **S-2.10.4 — cast cluster merge-pass** (`media/cast.py`,
  `_merge_oversplit_clusters`): a centroid-level second pass between
  `_cluster_faces` and the group/crowd loop. Two clusters merge when their
  L2-normalized centroids are cosine ≥ `_DEFAULT_CLUSTER_MERGE_THRESHOLD` (0.92,
  tighter than the per-crop cluster threshold). Guards against false merges:
  embeddingless singletons never merge, and **two clusters that share a photo are
  never merged** (the same person rarely appears twice in one frame). Default-on
  (`merge_oversplit=True`); inert on already-clean clusters.

- **S-2.10.6 — capture-day stratified budget** (`stage4_prefilter.py`,
  `_stratified_take`): **A/B-gated OFF** (`PreFilterOverrides.stratify_by_capture_day`,
  default False). When on, the remaining budget after reservations is allocated
  across capture-days — a per-day floor (`stratified_min_per_day`, default 3),
  then round-robin over days with spare capacity — returning exactly the budget
  in rank order. **One budget owner:** destination reservations (S-2.10.5) are
  taken *first*; the stratifier only distributes the remainder, never a second
  reserve.

## Consequences

- The merge-pass repairs cast coverage before the group/crowd math; a backend
  change (gemini caption-embed vs insightface) may want a re-tuned threshold —
  it is a kwarg for exactly that.
- Stratification can *hurt* quality when one day genuinely holds all the best
  moments (the floor forces weaker later-day shots), so it ships OFF pending a
  real multi-day eval; flag-off byte-matches the current global top-K.
- Both are deterministic, no-LLM, and log their drops (`cast_merge`,
  `stratified_day_budget`) for the inspect UI.
