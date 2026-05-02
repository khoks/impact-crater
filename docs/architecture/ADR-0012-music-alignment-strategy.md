# ADR-0012 — Music alignment strategy

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-02
**Phase:** scaffolding

## Context

D-010 fixed the two music-related modes for Story Video: **standard** (background music under curated video) and **music-video** (music drives the sequencing — cuts align with beats; section structure of music maps to media segments). D-018 fixed music sourcing as **user-supplied only at MVP** (royalty-free pack and licensed-library integration deferred to v1). A-013 originally classified section-to-media natural-language mapping as v1 — round-2 grooming pulled it into MVP per Q10.

Three round-2 redirects shape this ADR:

- **Beat detection accuracy matters** for music-video mode (cuts off the beat are immediately visible), so the heavier state-of-the-art beat detector is preferred over the convenient lighter one. Per Q8: **Madmom**.
- **Music duration mismatch handling is agentic at runtime** per Q9 — the orchestrator picks fade / loop / truncate-at-section based on the music + target_duration combination, not a fixed default.
- **Section-to-media NL mapping is in MVP** per Q10 — full power, not the simpler "free-text hint" version. The user's natural-language spec (e.g., "intro = scenic shots; chorus = summit footage; bridge = friends laughing; outro = sunset") is a first-class input to the N-001 narrative judge.

## Decision

### Audio ingest

- **Formats:** mp3, wav, m4a, flac, aac, ogg. Decoded via ffmpeg.
- **Probe at ingest:** ffprobe → duration, sample rate, channel count, bit rate; stored in the `media` SQLite row (audio gets a `media_type='audio'` and otherwise the same shape as photo/video).
- **Working format for analysis:** decode to 22050 Hz mono WAV in memory (downsample for analysis — full sample rate is overkill for beat / section / energy analysis).
- **Cache** at `~/.impact-crater/cache/{content_hash}/audio_analysis/` keyed by content-hash + analysis-pipeline-version.

### Music structure analysis

The pipeline produces a `MusicAnalysis` object via two libraries side-by-side:

- **Beat / downbeat detection: Madmom** (`madmom.features.beats.RNNBeatProcessor` + `madmom.features.downbeats.RNNDownBeatProcessor`). State-of-the-art beat tracking; accurate beat + downbeat timestamps at the millisecond level.
- **Section detection + energy curve: librosa** (`librosa.segment.agglomerative` + `librosa.feature.rms`). Madmom is beat-focused, not section-focused; librosa.segment is the standard for section/structural boundaries (intro / verse / chorus / bridge / outro). Energy curve (RMS over time, Gaussian-smoothed) drives intensity-aware placement.

Output schema:

```python
class MusicAnalysis(BaseModel):
    duration_ms: int
    bpm: float
    bpm_stability: float                      # how variable the tempo is
    beats_ms: list[int]                       # all beat timestamps
    downbeats_ms: list[int]                   # downbeat timestamps (bar starts)
    sections: list[Section]                   # ordered, contiguous, covering full duration
    energy_curve: list[float]                 # RMS values, sampled at 100 Hz (10ms resolution)
    spectral_novelty: list[float]             # 100 Hz; for accent / drop detection

class Section(BaseModel):
    label: str                                # "intro", "verse", "chorus", "bridge", "outro", "other"
    start_ms: int
    end_ms: int
    energy_mean: float
    energy_std: float
```

Section labels come from a heuristic mapping over librosa's structural-feature clustering: longest repeated segments labeled "chorus"; bookend segments labeled "intro"/"outro"; in-between segments labeled "verse" or "bridge" by position. Mislabeling is acceptable at MVP — the user's section-to-media NL mapping (below) doesn't *require* the labels to be canonically correct; the LLM judge sees the raw structure too.

**Library swappability:** the `MusicAnalyzer` is an abstraction (similar to `LLMClient` per ADR-0007). MVP implements `MadmomLibrosaAnalyzer` against the protocol. If Madmom's maintenance becomes problematic — its release cadence has slowed — swapping to BeatNet or a more recent beat tracker is a registry-level change, not a call-site refactor.

### Beat-grid generation

For music-video mode, derive a **cut-grid** from the beat detection:

- **Default cut frequency:** every 4 beats (1 bar at 4/4 time signature). For 120 BPM, that's a cut every 2.0 seconds.
- **Tempo-aware adjustment:**
  - Slow tempo (<80 BPM): 2-bar cuts (every 8 beats) to avoid choppiness.
  - Moderate tempo (80–140 BPM): default 1-bar cuts.
  - Fast tempo (>140 BPM): 2-bar cuts to keep clip durations reasonable.
- **Section-boundary snapping:** if a default cut would land within 200ms of a section boundary, snap the cut to the boundary.
- **User override:** the effort-level UX (D-013) lets the user pick "more cuts" / "fewer cuts" within a sensible range (½× to 2× the default frequency).

Output: `CutGrid{ cut_points_ms: list[int], section_aligned_cuts: list[int] }` consumed by ADR-0011 Stage 6 plan compilation.

### Section-to-media NL mapping (A-013, full version in MVP per Q10)

The user can describe section-to-media placement in natural language at job-creation time. Example:

> "Intro should be slow scenic shots — sky, mountains, the road we drove. Chorus is the summit attempt — the climbing footage. Bridge should be the rest stop with the kids playing. Outro is the sunset shots from the way back."

This is captured as a free-text field on the project. At Stage 5 (narrative-arc judgment, ADR-0011), the prompt to the Tier-L Opus call assembles:

1. The candidate set's metadata.
2. The brief verbatim.
3. The `MusicAnalysis` object — beats, downbeats, sections, energy curve.
4. **The user's section-to-media NL spec verbatim.**
5. The mode (music-video).
6. Target duration.

The Tier-L judge produces `ArcJudgment` with the `section_mapping` field populated: each music section maps to selected_item indices, and the `arc_reasoning` explains how the user's spec was honored (or where it couldn't be — "no clear summit-attempt footage in the candidate set; chorus uses the climbing approach footage instead, with notes flagged for refine").

The user's NL spec is pure context — no parsing into structured sections required. This sidesteps the "parse the user's prose" problem entirely; the Opus-tier judge handles it natively. Section labels in `MusicAnalysis` may be heuristic, but the user's prose grounds the placement.

**Why this is full-MVP and not v1:**

- The Tier-L Opus judge already needs the user's brief in prose form; adding a section spec is one more prose field, not a new pipeline stage.
- The cost is in the Opus call's input tokens, marginal at one extra paragraph.
- The architectural impact is zero new components.

### Music duration mismatch handling (agentic per Q9)

When `target_duration` doesn't match `music.duration`, the orchestrator picks a strategy at runtime via a Tier-M tool call. Tools available:

- `analyze_music_duration_mismatch(music, target_duration) → DurationStrategy`

```python
class DurationStrategy(BaseModel):
    strategy: Literal["fade_out", "loop_with_crossfade", "truncate_at_section", "loop_then_truncate"]
    rationale: str                            # surfaced to user via cost-transparency UI
    parameters: dict                          # strategy-specific params
```

The orchestrator's reasoning considers:

- **Music longer than target:**
  - If target is within 5% of a section boundary → `truncate_at_section` (cleanest ending).
  - If target is mid-section → `fade_out` at target_duration (preferred default for graceful endings).
  - If user explicitly asked for "use the whole song" via brief or refinement → don't truncate; adjust target_duration upward (with user confirmation).
- **Music shorter than target:**
  - If music has a clear loopable section (chorus or outro) → `loop_with_crossfade` at the loop boundary.
  - If music doesn't loop cleanly → `loop_then_truncate` (loop the music; fade out at target_duration).
  - If target ≪ music duration only marginally → suggest the user accept a slightly-shorter target to avoid awkward looping.
- **Music ≈ target:** no adjustment; use as-is.

The chosen strategy is recorded on the snapshot and explained to the user in the cost-transparency UI: "Using fade-out at 90s because the music is 4:12 and clean section boundaries near 90s aren't available."

This pushes more decision-making into the orchestrator's tool surface (formalized in ADR-0014 round 3). The `analyze_music_duration_mismatch` tool is one of the orchestrator's tool calls during job processing.

### Render-time alignment

Per ADR-0010 the render is ffmpeg-driven from the `RenderPlan` (ADR-0011 Stage 6). For music alignment specifically:

- **Standard mode:**
  - Audio mixed under entire video at -16 LUFS target loudness (YouTube-friendly).
  - Audio fades in over 1.5s at start, fades out per the chosen `DurationStrategy`.
  - No beat-snapping of cuts — the brief drives video pacing.
- **Music-video mode:**
  - Cuts snap to `CutGrid.cut_points_ms`.
  - Each clip's duration is `cut_points_ms[i+1] - cut_points_ms[i]`.
  - Photos in the timeline get duration from the snapped grid (no Ken Burns by default at MVP; effort-level UX can opt in).
  - Crossfades between clips on slow tempos; cuts on fast tempos (per beat-grid adjustment above).

### Two-pass loudness normalization

Both modes run an ffmpeg `loudnorm` two-pass at the final encode step. Target -16 LUFS / true-peak -1.5 dB / loudness range 11 — YouTube-friendly defaults that don't trigger broadcaster-grade re-encoding.

## Alternatives considered

- **librosa for beat detection (instead of Madmom).** Convenient (one library), but beat detection accuracy is materially lower than Madmom's RNN-based approach. For music-video mode where cuts off the beat are immediately visible, the accuracy gap matters. Rejected per Q8.
- **BeatNet or other recent beat detector.** Newer than Madmom and actively maintained. Considered as a fallback if Madmom maintenance becomes problematic; the `MusicAnalyzer` abstraction makes this a registry-level swap. Not chosen at MVP because Madmom's accuracy is well-known and stable.
- **Fixed default for duration mismatch (e.g., always fade-out).** Simpler. Rejected per Q9 — different music + target combinations want different strategies; the orchestrator can pick the right one per case.
- **Loop the music infinitely under a long target.** Rejected as a default — gets boring. Loop-with-crossfade or fade-out are smarter.
- **Section-to-media NL parsed into structured sections at job creation.** Considered. Rejected — the parse is exactly what the Tier-L Opus judge does naturally with the prose context. Adding a structured-parse stage is unnecessary intermediate work.
- **Section-to-media NL deferred to v1 (the original A-013 classification).** The simpler MVP version was "free-text hint passed to Stage 5 narrative judge" with no special handling. Rejected per Q10 — pulling the full version into MVP is one prose field; the Opus-tier judge handles it natively; no architectural debt.
- **Music sourcing widened in MVP (royalty-free starter pack).** Out of scope for ADR-0012; D-018 holds. Royalty-free + licensed-library land in v1.

## Consequences

- **Madmom is a heavier dependency than librosa.** Includes C extensions (some compile from source on certain platforms). The CI / packaging story for the wheel needs to handle this — pre-built wheels exist on PyPI for the common platforms, but edge cases (Apple Silicon at certain Python versions) may need attention. If install friction proves real, swap to BeatNet via the `MusicAnalyzer` abstraction.
- **Madmom maintenance has slowed in recent years** — last major release in early 2024. The architecture doesn't depend on Madmom-specifically; a swap to BeatNet or another recent beat tracker is a registry-level change. The `MusicAnalyzer` abstraction is the insurance.
- **Section labels from librosa are heuristic.** Mislabels happen ("verse" labeled "chorus" or vice versa). The user's NL spec grounds placement; the labels are advisory.
- **The `analyze_music_duration_mismatch` tool is a new orchestrator tool.** ADR-0014 (round 3) formalizes the orchestrator's tool surface; this tool joins it. Marginal cost — one Tier-M call per job.
- **Section-to-media NL spec is a single prose field on the project.** No new schema; lives alongside the brief. UI surface = one extra textarea at job creation, optional.
- **Two-pass loudness normalization adds ~10s to render time** at MVP scale. Acceptable; YouTube-friendly loudness is worth it.
- **A-013 reclassification (v1 → MVP) is recorded as D-031** and propagated into GROOMED_FEATURES.md + MVP.md + RECOMMENDED_ADDITIONS.md by the same round-2 PR.

## Linked items

- D-010 (music modes — standard + music-video), D-018 (user-supplied music at MVP), A-013 (music-video output mode — section-to-media NL mapping pulled into MVP per Q10), D-014 (target-duration is per-job knob), D-022 (refine pass — runs Stage 9 of ADR-0011 if user picks Refine after preview).
- ADR-0007 (`LLMClient` protocol — Tier-M call for duration strategy), ADR-0009 (per-operation routing — duration-strategy is a Tier-M call), ADR-0010 (ffmpeg used here for ingest decode + render), ADR-0011 (curation engine — beat-grid + section-mapping consumed at Stages 5/6).
- Cascades to: ADR-0014 (orchestrator harness — `analyze_music_duration_mismatch` joins the tool surface), ADR-0015 (resource accounting — duration-strategy choice surfaced via cost-transparency UI).
- Decision-log entries: D-030 (this ADR), D-031 (A-013 v1 → MVP scope reclassification, filed in the same round-2 PR).
- Project task: T-1.3.2.3 in [`project/tasks/`](../../project/tasks/T-1.3.2.3-adr-0012-music-alignment.md).
