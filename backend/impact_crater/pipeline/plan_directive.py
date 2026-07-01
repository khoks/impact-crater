"""PlanDirective — the shared duration/positional/tempo shaping contract (ADR-0019).

Stage 6 (`compile_plan`) consumes a `PlanDirective` as the single source of truth
for how clips are timed. The refinement layer (`stage9_refine`) emits a *partial*
directive that is deep-merged over the plan's persisted one and re-run through the
same Stage 6 code — so an initial render and a refined re-render are pixel-identical
where the directive matches.

`DEFAULT_DIRECTIVE` reproduces the pre-directive hard-coded constants exactly, so
every field is a no-op until a lever is populated. Kept dependency-light (pydantic
+ MusicAnalysis only, no RenderClip) so both stage6_plan and stage9_refine import
it without a cycle — the *application* of a directive to RenderClips lives in
stage6_plan.py, which imports this module.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from impact_crater.media.music import MusicAnalysis

# Defaults mirror the former stage6_plan module constants (S-2.11.1 / S-2.11.4).
_PHOTO_MIN_MS = 1000
_PHOTO_MAX_MS = 3000
_VIDEO_MIN_MS = 2000
_MONTAGE_MIN_MS = 2000
_MONTAGE_MAX_MS = 4000
_MAX_CLIPS_PER_LOCATION = 3

_MULT_LO, _MULT_HI = 0.6, 1.6  # clamp on any derived/emitted multiplier


class DurationBands(BaseModel):
    """Per-kind (min, max) display-duration band in ms. Defaults == today's."""

    model_config = ConfigDict(extra="ignore")
    photo_min_ms: int = _PHOTO_MIN_MS
    photo_max_ms: int = _PHOTO_MAX_MS
    video_min_ms: int = _VIDEO_MIN_MS
    montage_min_ms: int = _MONTAGE_MIN_MS
    montage_max_ms: int = _MONTAGE_MAX_MS


class PositionalRule(BaseModel):
    """Lever (a): a duration edit keyed by a timeline REGION (fraction 0..1).

    A clip whose *center* falls in `region` gets `multiplier` then `delta_ms`
    (re-clamped to its band). `neighbor_*` shapes the clips just outside the
    region so "make the opener longer AND shrink the photos around it" is one rule.
    """

    model_config = ConfigDict(extra="ignore")
    region: tuple[float, float] = (0.0, 0.2)
    multiplier: float = 1.0
    delta_ms: int = 0
    neighbor_multiplier: float = 1.0
    neighbor_delta_ms: int = 0
    neighbor_span: float = 0.05
    # A positional emphasis may need to exceed the normal band for its region.
    raises_band: bool = False
    label: str = ""


class TempoBand(BaseModel):
    """One slice of the song with a target pacing, derived from its energy."""

    model_config = ConfigDict(extra="ignore")
    start_frac: float = 0.0
    end_frac: float = 1.0
    duration_multiplier: float = 1.0  # <1 = snappier under high energy
    density_multiplier: float = 1.0  # >1 = pack more clips here (density lever)
    source: str = ""


class TempoProfile(BaseModel):
    """Lever (b): the song's pacing curve as ordered TempoBands. Empty == off."""

    model_config = ConfigDict(extra="ignore")
    bands: list[TempoBand] = Field(default_factory=list)
    # First cut ships duration-only (safe, no clip-count change). Density
    # shaping (reselect/thin) is a gated follow-on — it collides with Stage-4/5
    # selection + coverage, so it stays off until explicitly enabled.
    apply_density: bool = False


class SoftAlignSpec(BaseModel):
    """Lever (c) / S-2.11.6: nudge STANDARD-mode boundaries onto section starts."""

    model_config = ConfigDict(extra="ignore")
    enabled: bool = False
    section_starts_ms: list[int] = Field(default_factory=list)
    window_ms: int = 400


class PlanDirective(BaseModel):
    """The single shaping contract Stage 6 consumes and refinement emits.

    Every field defaults to a no-op, so `DEFAULT_DIRECTIVE` == the pre-directive
    behaviour. Refinement emits a PARTIAL directive deep-merged over the plan's
    persisted one via `merge_directive`.
    """

    model_config = ConfigDict(extra="ignore")
    schema_version: int = 1
    bands: DurationBands = Field(default_factory=DurationBands)
    max_clips_per_location: int = _MAX_CLIPS_PER_LOCATION
    positional_rules: list[PositionalRule] = Field(default_factory=list)
    tempo: TempoProfile = Field(default_factory=TempoProfile)
    soft_align: SoftAlignSpec = Field(default_factory=SoftAlignSpec)
    provenance: str = "default"  # default | music | refine | second_guess


DEFAULT_DIRECTIVE = PlanDirective()


def _clamp_mult(v: float) -> float:
    return max(_MULT_LO, min(_MULT_HI, float(v)))


def merge_directive(base: PlanDirective, patch: PlanDirective) -> PlanDirective:
    """Deep-merge a partial `patch` over `base`.

    A scalar/sub-model field that the patch changed from its pydantic default
    wins; a non-empty patch list replaces the base's list. Returns a new
    directive. This lets successive refinements compound (slow the intro, then
    later punch the ending) without losing prior shaping.
    """
    default = PlanDirective()
    out = base.model_copy(deep=True)

    if patch.bands != default.bands:
        out.bands = patch.bands.model_copy(deep=True)
    if patch.max_clips_per_location != default.max_clips_per_location:
        out.max_clips_per_location = patch.max_clips_per_location
    if patch.positional_rules:
        # Append positional rules so a new emphasis doesn't wipe an earlier one,
        # but drop any base rule whose region+label matches (re-edit same spot).
        keys = {(tuple(r.region), r.label) for r in patch.positional_rules}
        kept = [r for r in out.positional_rules if (tuple(r.region), r.label) not in keys]
        out.positional_rules = kept + list(patch.positional_rules)
    if patch.tempo != default.tempo:
        out.tempo = patch.tempo.model_copy(deep=True)
    if patch.soft_align != default.soft_align:
        out.soft_align = patch.soft_align.model_copy(deep=True)
    if patch.provenance != default.provenance:
        out.provenance = patch.provenance
    return out


def build_directive_from_music(
    analysis: MusicAnalysis, *, target_ms: int, half_split: bool = True
) -> PlanDirective:
    """Derive a duration-shaping directive from the song (lever b + c seed).

    Splits the track into halves (robust to noisy librosa section detection);
    the higher-energy half gets `duration_multiplier < 1` (snappier photos) and a
    `density_multiplier > 1`. Also seeds `soft_align.section_starts_ms` from the
    detected sections (left disabled until S-2.11.6 turns it on). Density stays
    off (`apply_density=False`) in this first cut.
    """
    curve = analysis.energy_curve or []
    bands: list[TempoBand] = []
    if curve and half_split:
        mid = len(curve) // 2 or 1
        first = curve[:mid]
        second = curve[mid:] or first
        m1 = sum(first) / len(first) if first else 0.0
        m2 = sum(second) / len(second) if second else 0.0
        overall = (m1 + m2) / 2 or 1.0
        for lo, hi, mean, tag in ((0.0, 0.5, m1, "energy_half:first"), (0.5, 1.0, m2, "energy_half:second")):
            ratio = mean / overall if overall else 1.0
            # More energetic half → shorter clips, higher density.
            bands.append(
                TempoBand(
                    start_frac=lo,
                    end_frac=hi,
                    duration_multiplier=_clamp_mult(1.0 / ratio if ratio else 1.0),
                    density_multiplier=_clamp_mult(ratio),
                    source=tag,
                )
            )

    section_starts = sorted({int(s.start_ms) for s in analysis.sections if 0 < s.start_ms < target_ms})

    return PlanDirective(
        tempo=TempoProfile(bands=bands, apply_density=False),
        soft_align=SoftAlignSpec(enabled=False, section_starts_ms=section_starts, window_ms=400),
        provenance="music",
    )
