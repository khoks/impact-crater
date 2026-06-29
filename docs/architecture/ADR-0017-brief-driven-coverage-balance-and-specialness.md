# ADR-0017 — Brief-driven coverage & balance, specialness-aware Stage 4, and the Stage 5 coverage contract

Status: **accepted** (2026-06-29). Amends the Stage 4 selection and Stage 5 input sections of [ADR-0011](./ADR-0011-curation-engine-algorithm.md).

## Context

Inspecting the real 1,663-asset Southwest-US-trip job (snapshot `b4b73c7b1fe044b7`) against its media surfaced systematic curation defects, all rooted in the same gap — **Stage 4 and the Stage 5 judge fly blind on structured intent**:

- **Las Vegas (a named destination) was dropped entirely.** The brief lists five destinations incl. "las vegas"; `prefilter()` takes no brief, so all 37 Nevada-area shots (incl. a good Hoover Dam landmark, specialness 0.72) lost the single global top-K rank and never reached the judge. The judge only flagged Vegas in `open_questions`.
- **Zero video in a "highlight video."** 58 video scenes survived Stage 4 but the judge selected none, because every candidate was presented as a still (no media-type marker; the already-computed `scene_summary` was discarded).
- **Monotonous, people-heavy climax.** Six near-identical "family-at-Grand-Canyon-golden-hour" shots in a row; nothing capped intra-section similarity or balanced people vs landscape or per-location share.
- **Specialness computed but unused.** Stage 3 pays Tier-M for a `specialness_score`, but Stage 4's `combined_score`, quality floor, and dedup tie-breaks all ignored it — so the most special member of a burst could be discarded and high-specialness shots ranked out.
- **Backwards opener.** The opener was a later day than the next clip, against a "roughly chronological" brief.

## Decision

1. **Brief becomes structured intent, before Stage 4.** A brief-parse step (Stage 0.5) runs after ingest (can run concurrent with Stage 2), reusing the existing `parse_user_brief` route with a `BRIEF_SCHEMA` that adds `named_destinations` (name/aliases/kind/chronological_hint) and a `chronological` flag, producing a `BriefIntent` threaded into Stage 4 and Stage 5. Fail-soft (empty intent → prior behaviour). [S-2.10.5]

2. **Stage 4 stays no-LLM but gains specialness + coverage + balance:**
   - `combined_score` is 4-term `(0.25 quality, 0.40 narrative, 0.20 specialness, 0.15 diversity)`; narrative stays dominant so the brief still steers. Specialness participates in dedup, semantic best-of-burst, and location-cap tie-breaks, and a high-specialness shot (≥0.75) is rescued past the hard quality floor. [S-2.10.2, **implemented**]
   - Named-destination **coverage reservation**: the top 1–2 assets per named destination are reserved (inviolable) before the cut and tagged `dest=<name>`; a single `destination_coverage`/CoveragePlan object is emitted on `CandidateSet`. [S-2.10.5]
   - The global top-K is replaced by a **capture-day stratified proportional budget** (largest-remainder, `min_per_bucket=1`) that consumes the reservations as inviolable seeds — ONE budget mechanism, no double-budgeting. [S-2.10.6]

3. **Stage 5 judge consumes the contract via prompt only (no new pipeline step, no second pass).** Candidates are tagged `MOTION(video clip)`/`STILL(photo)` with `motion_summary=`; the prompt enforces a video-share floor, an intra-section variety cap, role/people-landscape/location balance, a chronological-flag-gated strict-forward-after-opener rule, and a HARD per-named-destination coverage requirement (or an honest open_question when a place has no media). [S-2.10.3, **prompt/representation implemented**]

4. **The single Opus judge is retained.** Splitting into shot-list + ordering or adding a re-rank/second judge was rejected: the judge is not overloaded at ~621 candidates, splitting doubles Tier-L cost and creates a hand-off that can't reconsider a bad selection. The real defect was missing structured input, not judge capacity.

## Consequences

- Stage 4 selection changes for every job (specialness now 20% of the score; coverage reservation + stratified budget once S-2.10.5/6 land) — this shifts which candidates reach the cached Stage 5 signature, so affected jobs re-run Stage 5. Validated against the known-good 23-shot arc before locking thresholds; the stratified budget (S-2.10.6) ships behind its own A/B-validated PR because parity-for-quality is a real regression risk (`min_per_bucket=1` guarantees presence, not parity).
- One extra Tier-M `parse_user_brief` call per job (cached by brief hash; ~$0.005) — negligible.
- The deeper variety/dedup weakness (near-identical shots only diverge enough in *caption* to survive dedup) is NOT fixed here — it is rooted in the caption-then-embed workaround and addressed separately by a local image embedder ([ADR-0018](./ADR-0018-local-image-embedder.md)).
- Stage 4 remains deterministic and unit-testable; all new behaviour is overridable via `PreFilterOverrides`.

Linked: E-2.10, S-2.10.2/3/5/6, S-2.9.20 (Las Vegas absent — resolved by the coverage guarantee), D-053, A-023 (feedback loop that surfaced these).
