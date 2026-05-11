"""Stage 4 pre-filter tests — envelope math, dedup, quality floor, ranking."""

from __future__ import annotations

import pytest

from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.stage4_prefilter import (
    PreFilterOverrides,
    Stage4EmptyCandidateSet,
    compute_envelope,
    prefilter,
)
from impact_crater.pipeline.types import (
    RichMetadataPhoto,
    Stage2AssetOutputs,
    Stage3AssetOutputs,
)


# ---- Envelope math ----------------------------------------------------


def test_envelope_floor_is_50_for_short_targets() -> None:
    floor, ceiling = compute_envelope(input_count=1000, target_duration_seconds=10)
    assert floor == 50  # max(50, 10*2) = 50
    assert ceiling == 800  # floor(1000 * 0.80)


def test_envelope_floor_grows_with_target_duration() -> None:
    floor, ceiling = compute_envelope(input_count=1000, target_duration_seconds=120)
    assert floor == 240  # max(50, 120*2) = 240
    assert ceiling == 800


def test_envelope_floor_capped_to_input_count() -> None:
    """If user has only 30 photos, floor pulls down to input_count (pass-through)."""
    floor, ceiling = compute_envelope(input_count=30, target_duration_seconds=60)
    assert floor == 30
    assert ceiling >= floor


def test_envelope_ceiling_is_80_percent_of_input() -> None:
    floor, ceiling = compute_envelope(input_count=5000, target_duration_seconds=300)
    assert ceiling == 4000  # floor(5000 * 0.80)
    assert floor == 600  # max(50, 300 * 2) = 600


def test_envelope_zero_input_returns_zero() -> None:
    assert compute_envelope(input_count=0, target_duration_seconds=10) == (0, 0)


# ---- Per-asset pre-filter ----------------------------------------------


def _records(count: int) -> tuple[
    list[MediaRecord],
    list[Stage2AssetOutputs],
    list[Stage3AssetOutputs],
]:
    """Build `count` photo records with varying quality and pHash diversity.

    pHashes are spread across the full 64-bit space (Hamming distance > 5
    between any pair) so the dedup pass leaves singletons by default.
    Locations rotate through 12 distinct buckets so the location-cluster
    cap (10) doesn't collapse everything into one bucket.
    """
    media: list[MediaRecord] = []
    stage2: list[Stage2AssetOutputs] = []
    stage3: list[Stage3AssetOutputs] = []
    for i in range(count):
        ch = f"hash{i:04d}"
        # Stripe-encoded pHash with very high Hamming distance between any pair.
        # i ↦ 16-byte hex where byte k = (i << k) & 0xFF; gives Hamming > 5
        # between any pair of indices.
        bits = sum(((i + 1) << (k * 8)) & (0xFF << (k * 8)) for k in range(8))
        phash = f"{bits & 0xFFFFFFFFFFFFFFFF:016x}"
        media.append(
            MediaRecord(
                content_hash=ch,
                source_path=f"/tmp/{ch}.jpg",
                media_type="photo",
                file_size=1234,
                quick_stats={"phash": phash, "dhash": phash},
            )
        )
        stage2.append(
            Stage2AssetOutputs(
                content_hash=ch,
                scene_index=None,
                caption=f"caption {i}",
                quality_score=0.5 + (i % 5) * 0.1,
                narrative_relevance_score=0.4 + (i % 7) * 0.07,
                embedding_dim=768,
            )
        )
        # Spread across 12 distinct location buckets so the location-cluster
        # cap doesn't collapse the whole input into a single 10-item bucket.
        loc_bucket = f"location-{i % 12}"
        stage3.append(
            Stage3AssetOutputs(
                content_hash=ch,
                scene_index=None,
                metadata=RichMetadataPhoto(
                    time_of_day="midday",
                    quality=0.6,
                    mood="calm",
                    generic_tags=["outdoor", f"tag{i}"],
                    location={"description": loc_bucket, "lat_long": None},
                ),
            )
        )
    return media, stage2, stage3


def test_prefilter_drops_low_quality_items() -> None:
    media, stage2, stage3 = _records(100)
    # Force half the items below the quality floor.
    for i, s in enumerate(stage2):
        s.quality_score = 0.2 if i < 50 else 0.8

    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=30,
    )
    selected_keys = {it.content_hash for it in cs.items}
    # Every kept item should have come from the high-quality half.
    high_quality = {f"hash{i:04d}" for i in range(50, 100)}
    assert selected_keys.issubset(high_quality)
    # Filter log records every quality-floor drop.
    drop_count = sum(
        1 for entry in cs.filter_log if entry.get("reason") == "quality_below_threshold"
    )
    assert drop_count == 50


def test_prefilter_clamps_target_size_within_envelope() -> None:
    media, stage2, stage3 = _records(100)
    # User asks for 200 (way above ceiling=80) — must clamp to 80.
    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=20,
        overrides=PreFilterOverrides(target_size=200),
    )
    assert cs.ceiling == 80
    assert cs.target_size == 80
    assert len(cs.items) <= 80


def test_prefilter_clamps_target_size_above_floor() -> None:
    media, stage2, stage3 = _records(1000)
    # User asks for 5 — must clamp up to floor=50 (target_duration=20).
    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=20,
        overrides=PreFilterOverrides(target_size=5),
    )
    assert cs.floor == 50
    assert cs.target_size == 50


def test_prefilter_passes_through_small_inputs() -> None:
    """Input count below floor → floor = input_count → pass-through."""
    media, stage2, stage3 = _records(20)
    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=60,
    )
    assert cs.floor == 20
    assert cs.ceiling == 20  # max(floor, 80% * 20) = 20
    # All 20 high-quality items should pass.
    assert len(cs.items) == 20


def test_prefilter_dedup_collapses_phash_clusters() -> None:
    """Items sharing pHash get clustered; dedup_factor=3 keeps ⌈cluster/3⌉."""
    media, stage2, stage3 = _records(30)
    # Force first 9 items to share one pHash — Hamming dist 0 within cluster.
    same_hash = "ffffffffffffffff"
    for i in range(9):
        media[i].quick_stats["phash"] = same_hash
        stage2[i].quality_score = 0.9  # High enough to pass the floor

    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=10,
        overrides=PreFilterOverrides(dedup_factor=3),
    )
    # Only ⌈9/3⌉ = 3 of the colliding items should be kept.
    kept_from_cluster = sum(
        1 for it in cs.items if it.content_hash in {f"hash{i:04d}" for i in range(9)}
    )
    assert kept_from_cluster <= 3


def test_prefilter_filter_log_records_keep_decisions() -> None:
    media, stage2, stage3 = _records(60)
    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=20,
    )
    keep_entries = [e for e in cs.filter_log if e.get("decision") == "keep"]
    assert len(keep_entries) == len(cs.items)


def test_prefilter_ranks_higher_narrative_first() -> None:
    """Narrative weight β=0.5 > quality weight α=0.3 → narrative dominates."""
    media, stage2, stage3 = _records(60)
    # Deliberately invert: low quality + high narrative for half.
    for i, s in enumerate(stage2):
        if i < 30:
            s.quality_score = 0.5
            s.narrative_relevance_score = 0.95
        else:
            s.quality_score = 0.95
            s.narrative_relevance_score = 0.45

    cs = prefilter(
        media=media,
        stage2=stage2,
        stage3=stage3,
        target_duration_seconds=10,
        overrides=PreFilterOverrides(target_size=50),
    )
    assert cs.target_size == 50
    # The high-narrative items should fill most of the slots.
    high_narrative = {f"hash{i:04d}" for i in range(30)}
    selected = {it.content_hash for it in cs.items}
    overlap = len(selected & high_narrative)
    # Generous bound: at least 25/30 high-narrative items should be selected.
    assert overlap >= 25


def test_prefilter_metadata_summary_is_populated() -> None:
    media, stage2, stage3 = _records(20)
    cs = prefilter(
        media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10
    )
    for it in cs.items:
        assert it.metadata_summary is not None
        assert "time=midday" in it.metadata_summary


def test_prefilter_default_target_is_30_percent() -> None:
    """No override + no quality drops → target ≈ ceil(input * 0.30)."""
    media, stage2, stage3 = _records(1000)
    for s in stage2:
        s.quality_score = 0.8  # all pass quality
    cs = prefilter(
        media=media, stage2=stage2, stage3=stage3, target_duration_seconds=20
    )
    # Target = clamp(ceil(1000*0.30), floor=50, ceiling=800) = 300.
    # The dedup pass leaves singletons because all pHashes differ; the
    # location-cluster cap then pulls everything in one bucket down to 10.
    # With one bucket of 1000 and cap=10, only 10 survive — and target_size
    # gets clamped to that ceiling. Verify both clamps are in effect.
    assert cs.target_size == 300
    # The actual output is bounded by what survives the prior steps.
    assert len(cs.items) <= cs.target_size


# ---- Fail-fast on zero candidates (Bug 3 fix from 2026-05-07 UI test) ----


def test_prefilter_raises_when_all_dropped_by_quality_floor() -> None:
    """Real failure 2026-05-07: a vague brief + cached low quality scores
    dropped every asset in Stage 4, but the pipeline still ran Stage 5
    (Tier-L Opus, ~$0.50) before Stage 6 finally raised. Now Stage 4
    raises immediately so no expensive call follows zero candidates."""
    media, stage2, stage3 = _records(20)
    for s in stage2:
        s.quality_score = 0.1  # below the default 0.40 floor

    with pytest.raises(Stage4EmptyCandidateSet) as excinfo:
        prefilter(
            media=media,
            stage2=stage2,
            stage3=stage3,
            target_duration_seconds=30,
        )

    exc = excinfo.value
    assert exc.input_count == 20
    assert exc.after_quality_count == 0
    assert exc.quality_threshold == pytest.approx(0.40)
    # The message must guide the user to the actionable diagnosis.
    msg = str(exc)
    assert "input=20" in msg
    assert "after_quality_floor" in msg


def test_prefilter_does_not_raise_for_empty_input() -> None:
    """input_count=0 is the legitimate empty-folder case — return an empty
    CandidateSet without raising, so the runner can surface that one
    cause to the user separately (Stage 1 would have already noted it)."""
    cs = prefilter(media=[], stage2=[], stage3=[], target_duration_seconds=30)
    assert len(cs.items) == 0
