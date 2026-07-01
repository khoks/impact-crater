"""Tests for the PlanDirective shaping levers (S-2.12.1 / ADR-0019)."""

from __future__ import annotations

import pytest

from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.media.music import MusicAnalysis, Section
from impact_crater.pipeline import stage6_plan
from impact_crater.pipeline.plan_directive import (
    DEFAULT_DIRECTIVE,
    PlanDirective,
    PositionalRule,
    SoftAlignSpec,
    TempoBand,
    TempoProfile,
    build_directive_from_music,
    merge_directive,
)
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.stage6_plan import RenderClip, compile_plan
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


def _rc(ref: str, ms: int, *, kind: str = "photo", start: float = 0.0, end: float = 0.0) -> RenderClip:
    return RenderClip(
        candidate_ref=ref, kind=kind, source_path=f"/tmp/{ref}",  # type: ignore[arg-type]
        start_seconds=start, end_seconds=end, intended_duration_ms=ms, aspect_ratio_action="as_is",
    )


def test_default_directive_bands_match_legacy_constants() -> None:
    b = DEFAULT_DIRECTIVE.bands
    assert (b.photo_min_ms, b.photo_max_ms) == (1000, 3000)
    assert b.video_min_ms == 2000
    assert DEFAULT_DIRECTIVE.max_clips_per_location == 3
    # A photo clip's band from the default directive is the legacy (1000, 3000).
    assert stage6_plan._clip_band(_rc("a", 2000)) == (1000, 3000)


def test_merge_directive_appends_positional_and_overrides_scalars() -> None:
    base = PlanDirective(positional_rules=[PositionalRule(region=(0.0, 0.2), label="a")])
    patch = PlanDirective(
        positional_rules=[PositionalRule(region=(0.8, 1.0), label="b")],
        max_clips_per_location=5,
    )
    merged = merge_directive(base, patch)
    labels = {r.label for r in merged.positional_rules}
    assert labels == {"a", "b"}  # appended, not replaced
    assert merged.max_clips_per_location == 5  # scalar override wins
    # Re-editing the same region+label replaces rather than duplicates.
    patch2 = PlanDirective(positional_rules=[PositionalRule(region=(0.0, 0.2), label="a", delta_ms=500)])
    merged2 = merge_directive(base, patch2)
    a_rules = [r for r in merged2.positional_rules if r.label == "a"]
    assert len(a_rules) == 1 and a_rules[0].delta_ms == 500


def test_positional_opener_can_exceed_band_and_neighbor_shrinks() -> None:
    clips = [_rc(str(i), 2000) for i in range(6)]
    directive = PlanDirective(
        positional_rules=[
            PositionalRule(region=(0.0, 0.2), delta_ms=2000, raises_band=True,
                           neighbor_delta_ms=-500, neighbor_span=0.1, label="opener"),
        ]
    )
    shaped = stage6_plan._apply_positional(clips, directive, target_ms=12_000)
    scaled = stage6_plan._scale_to_target(shaped, target_ms=12_000, directive=directive)
    # The opener is held longer than the normal 3s photo cap (emphasis honoured)…
    assert scaled[0].intended_duration_ms > 3000
    # …and it is clearly longer than its shrunken neighbour.
    assert scaled[0].intended_duration_ms > scaled[1].intended_duration_ms


def test_tempo_profile_shortens_the_high_energy_half() -> None:
    clips = [_rc(str(i), 2000) for i in range(4)]
    directive = PlanDirective(
        tempo=TempoProfile(bands=[
            TempoBand(start_frac=0.0, end_frac=0.5, duration_multiplier=0.7),
            TempoBand(start_frac=0.5, end_frac=1.0, duration_multiplier=1.3),
        ])
    )
    out = stage6_plan._apply_tempo_profile(clips, directive, target_ms=8000)
    first_half = out[0].intended_duration_ms + out[1].intended_duration_ms
    second_half = out[2].intended_duration_ms + out[3].intended_duration_ms
    assert first_half < second_half


def test_soft_align_snaps_boundary_within_window_only() -> None:
    clips = [_rc("a", 1000), _rc("b", 1000), _rc("c", 1000)]
    directive = PlanDirective(
        soft_align=SoftAlignSpec(enabled=True, section_starts_ms=[1100], window_ms=400)
    )
    out = stage6_plan._soft_align_boundaries(clips, directive)
    assert out[0].intended_duration_ms == 1100  # snapped to the section start
    # A far section start would not move the boundary.
    far = PlanDirective(soft_align=SoftAlignSpec(enabled=True, section_starts_ms=[5000], window_ms=400))
    unchanged = stage6_plan._soft_align_boundaries(clips, far)
    assert unchanged[0].intended_duration_ms == 1000


def test_soft_align_disabled_is_noop() -> None:
    clips = [_rc("a", 1000), _rc("b", 1000)]
    out = stage6_plan._soft_align_boundaries(clips, DEFAULT_DIRECTIVE)
    assert [c.intended_duration_ms for c in out] == [1000, 1000]


def test_build_directive_from_music_shortens_loud_half_and_seeds_sections() -> None:
    analysis = MusicAnalysis(
        duration_ms=60_000, bpm=120.0, bpm_stability=0.9,
        beats_ms=[], downbeats_ms=[],
        sections=[
            Section(label="a", start_ms=0, end_ms=30_000, energy_mean=1.0, energy_std=0.1),
            Section(label="b", start_ms=30_000, end_ms=60_000, energy_mean=0.3, energy_std=0.1),
        ],
        energy_curve=[1.0] * 50 + [0.2] * 50,  # loud first half
        spectral_novelty=[0.0] * 100,
        analyzer="librosa-only",
    )
    directive = build_directive_from_music(analysis, target_ms=60_000)
    assert directive.provenance == "music"
    assert len(directive.tempo.bands) == 2
    # Louder first half → shorter clips there.
    assert directive.tempo.bands[0].duration_multiplier < 1.0
    assert directive.tempo.bands[1].duration_multiplier > 1.0
    assert directive.tempo.apply_density is False  # duration-only first cut
    assert 30_000 in directive.soft_align.section_starts_ms
    assert directive.soft_align.enabled is False  # seeded but off


async def test_compile_plan_persists_directive_and_round_trips(db_initialized: None) -> None:
    recs = [MediaRecord(content_hash=h, source_path=f"/tmp/{h}.jpg", media_type="photo",
                        file_size=1, quick_stats={"width": 1920, "height": 1080}) for h in ("a", "b")]
    arc = ArcJudgment(
        selected_items=[SelectedItem(candidate_ref="a", placement_position=0, intended_duration_ms=2000, role="", notes=""),
                        SelectedItem(candidate_ref="b", placement_position=1, intended_duration_ms=2000, role="", notes="")],
        arc_reasoning="t", confidence=0.7,
    )
    directive = PlanDirective(max_clips_per_location=5, provenance="music")
    plan = await compile_plan(
        arc_judgment=arc, ingest_records=recs, project_id="p-dir",
        target_duration_seconds=10, directive=directive,
    )
    assert plan.schema_version == 2
    assert plan.directive.max_clips_per_location == 5
    reloaded = stage6_plan.load_plan(plan.snapshot_id, "p-dir")
    assert reloaded.directive.max_clips_per_location == 5
    assert reloaded.directive.provenance == "music"
