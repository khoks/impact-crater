"""Stage 4 pre-filter tests — envelope math, dedup, quality floor, ranking."""

from __future__ import annotations

import pytest
from impact_crater.pipeline.brief_intent import BriefIntent, NamedDestination
from impact_crater.pipeline.destinations import ReservationSet
from impact_crater.pipeline.stage1_ingest import MediaRecord, SceneRecord
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

# ---- S-2.10.5 destination reservation (the Vegas fix) -----------------


def _vegas_scenario() -> tuple:
    """12 sharp distractors + 1 low-quality shot captioned 'las vegas strip'.
    The Vegas shot ranks below target_size and would be dropped without a
    reservation."""
    media: list[MediaRecord] = []
    stage2: list[Stage2AssetOutputs] = []
    stage3: list[Stage3AssetOutputs] = []
    specs = [(f"good{i:02d}", 0.95, f"a sharp landscape {i}", f"loc-{i}") for i in range(12)]
    specs.append(("vegas", 0.20, "the las vegas strip at night", "vegas"))
    for i, (ch, q, cap, loc) in enumerate(specs):
        phash = _spread_phash(i)
        media.append(MediaRecord(content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo",
                                 file_size=1, quick_stats={"phash": phash, "dhash": phash}))
        stage2.append(Stage2AssetOutputs(content_hash=ch, caption=cap, quality_score=q,
                                        narrative_relevance_score=0.5, embedding_dim=8))
        stage3.append(Stage3AssetOutputs(content_hash=ch,
                     metadata=RichMetadataPhoto(time_of_day="midday", location={"description": loc})))
    return media, stage2, stage3


def test_named_destination_survives_low_quality(monkeypatch) -> None:
    media, stage2, stage3 = _vegas_scenario()
    intent = BriefIntent(named_destinations=[NamedDestination(name="Las Vegas", aliases=["vegas"])])
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(target_size=8), brief_intent=intent)
    assert "vegas" in {it.content_hash for it in cs.items}  # reserved past the quality floor
    assert cs.cluster_metadata["must_keep_satisfied"] >= 1
    # The judge is told which candidate covers the destination.
    vegas_ref = next(it for it in cs.items if it.content_hash == "vegas")
    assert "dest:Las Vegas" in (vegas_ref.metadata_summary or "")
    # Coverage plan records the match for diagnostics.
    assert cs.coverage_plan is not None
    assert cs.coverage_plan.named_destinations[0].basis == "matched"


def test_refinement_reservation_reuses_the_same_mechanism() -> None:
    """The refinement layer passes a ReservationSet directly (no brief) — same
    force-keep, proving the shared lever."""
    media, stage2, stage3 = _vegas_scenario()
    res = ReservationSet(keys=frozenset({"vegas"}), reason_by_key={"vegas": "refine:keep vegas"},
                         source="refinement")
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(target_size=8), reservations=res)
    assert "vegas" in {it.content_hash for it in cs.items}


def test_reservation_none_is_unchanged() -> None:
    """Regression guard: no brief_intent / reservations → the low-quality Vegas
    shot is dropped exactly as before."""
    media, stage2, stage3 = _vegas_scenario()
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(target_size=8, quality_threshold=0.4))
    assert "vegas" not in {it.content_hash for it in cs.items}  # quality floor drops it


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


def _spread_phash(i: int) -> str:
    """Perceptual hash with Hamming distance > 5 between any two indices,
    so the pHash pass leaves them as singletons and the SEMANTIC pass is
    what gets exercised."""
    bits = sum(((i + 1) << (k * 8)) & (0xFF << (k * 8)) for k in range(8))
    return f"{bits & 0xFFFFFFFFFFFFFFFF:016x}"


def test_semantic_dedup_keeps_best_of_burst() -> None:
    """Three retakes (same embedding, same ~moment, but pHash-distinct
    angles) collapse to the single best-quality member; distinct shots
    survive (A-017)."""
    import numpy as np

    base = np.ones((8,), dtype=np.float32)
    distinct = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
    media: list[MediaRecord] = []
    stage2: list[Stage2AssetOutputs] = []
    stage3: list[Stage3AssetOutputs] = []
    # 3 retakes of one moment + 1 genuinely different shot.
    specs = [
        ("burst0", base, 0.6, "2026-04-05T16:31:21"),
        ("burst1", base, 0.9, "2026-04-05T16:31:24"),  # best quality
        ("burst2", base, 0.5, "2026-04-05T16:31:27"),
        ("other", distinct, 0.8, "2026-04-05T18:00:00"),
    ]
    for i, (ch, emb, q, ts) in enumerate(specs):
        phash = _spread_phash(i)
        media.append(
            MediaRecord(
                content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo",
                file_size=1, quick_stats={"phash": phash, "dhash": phash},
                capture_timestamp=ts, capture_source="exif",
            )
        )
        stage2.append(
            Stage2AssetOutputs(
                content_hash=ch, caption=ch, quality_score=q,
                narrative_relevance_score=0.6, embedding_dim=8, embedding=emb,
            )
        )
        stage3.append(
            Stage3AssetOutputs(
                content_hash=ch,
                metadata=RichMetadataPhoto(time_of_day="midday", location={"description": "trail"}),
            )
        )
    cs = prefilter(
        media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
        overrides=PreFilterOverrides(quality_threshold=0.0, target_size=10),
    )
    kept = {it.content_hash for it in cs.items}
    # The burst collapses to its best member only; the distinct shot stays.
    assert "burst1" in kept
    assert "other" in kept
    assert "burst0" not in kept and "burst2" not in kept
    drops = [e for e in cs.filter_log if e.get("reason") == "semantic_duplicate"]
    assert {d["key"] for d in drops} == {"burst0", "burst2"}
    best = next(it for it in cs.items if it.content_hash == "burst1")
    assert "burst_best_of=3" in (best.metadata_summary or "")


def test_semantic_dedup_respects_time_window() -> None:
    """Same embedding but captured far apart (recurring scenery on different
    days) must NOT be merged when timestamps are present."""
    import numpy as np

    emb = np.ones((8,), dtype=np.float32)
    media: list[MediaRecord] = []
    stage2: list[Stage2AssetOutputs] = []
    stage3: list[Stage3AssetOutputs] = []
    for i, ts in enumerate(["2026-04-05T09:00:00", "2026-04-07T09:00:00"]):
        ch = f"day{i}"
        phash = _spread_phash(i)
        media.append(
            MediaRecord(
                content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo",
                file_size=1, quick_stats={"phash": phash, "dhash": phash},
                capture_timestamp=ts, capture_source="exif",
            )
        )
        stage2.append(
            Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=0.7,
                              narrative_relevance_score=0.6, embedding_dim=8, embedding=emb)
        )
        stage3.append(
            Stage3AssetOutputs(content_hash=ch,
                              metadata=RichMetadataPhoto(time_of_day="morning",
                                                         location={"description": f"spot{i}"}))
        )
    cs = prefilter(
        media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
        overrides=PreFilterOverrides(quality_threshold=0.0, target_size=10),
    )
    # 2 days apart → both survive (window is 120s).
    assert {it.content_hash for it in cs.items} == {"day0", "day1"}


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


# ---- A-026 specialness-aware selection -------------------------------------


def _one(ch, *, quality, narrative=0.6, specialness=0.5, phash=None, ts=None, loc="spot"):
    rec = MediaRecord(
        content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo", file_size=1,
        quick_stats={"phash": phash or _spread_phash(abs(hash(ch)) % 1000), "dhash": "0"},
        capture_timestamp=ts, capture_source="exif" if ts else None,
    )
    s2 = Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=quality,
                            narrative_relevance_score=narrative, embedding_dim=8)
    s3 = Stage3AssetOutputs(content_hash=ch, metadata=RichMetadataPhoto(
        time_of_day="midday", specialness_score=specialness,
        location={"description": loc}))
    return rec, s2, s3


def test_specialness_rescues_soft_but_memorable_shot() -> None:
    """A-026: a soft (low-quality) but high-specialness shot survives the
    quality floor; a soft AND unremarkable one is dropped."""
    rows = [
        _one("special", quality=0.2, specialness=0.9),   # rescued
        _one("dull", quality=0.2, specialness=0.5),       # dropped
        _one("sharp", quality=0.8, specialness=0.5),      # normal keep
    ]
    media, stage2, stage3 = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(target_size=10))
    kept = {it.content_hash for it in cs.items}
    assert "special" in kept and "sharp" in kept
    assert "dull" not in kept
    rescues = [e for e in cs.filter_log if e.get("reason") == "specialness_rescue"]
    assert {e["key"] for e in rescues} == {"special"}


def test_specialness_wins_semantic_dedup_tiebreak() -> None:
    """A-026: within a burst, the most SPECIAL member is kept even when a
    near-duplicate is marginally sharper (the 0.95-specialness case)."""
    import numpy as np

    emb = np.ones((8,), dtype=np.float32)
    specs = [
        ("plain", 0.85, 0.40, "2026-04-05T16:31:21"),    # slightly sharper, dull
        ("hero", 0.80, 0.95, "2026-04-05T16:31:24"),     # the keeper
    ]
    media, stage2, stage3 = [], [], []
    for i, (ch, q, sp, ts) in enumerate(specs):
        media.append(MediaRecord(content_hash=ch, source_path=f"/tmp/{ch}.jpg",
            media_type="photo", file_size=1,
            quick_stats={"phash": _spread_phash(i), "dhash": "0"},
            capture_timestamp=ts, capture_source="exif"))
        stage2.append(Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=q,
            narrative_relevance_score=0.6, embedding_dim=8, embedding=emb))
        stage3.append(Stage3AssetOutputs(content_hash=ch, metadata=RichMetadataPhoto(
            time_of_day="midday", specialness_score=sp, location={"description": "trail"})))
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(quality_threshold=0.0, target_size=10))
    kept = {it.content_hash for it in cs.items}
    assert kept == {"hero"}  # the special one survives the burst, not the sharper-but-dull one


def test_filter_log_entries_carry_all_three_scores() -> None:
    """F8c: keep and rank-drop entries carry quality/narrative/specialness so
    the inspect UI can show why a borderline item was kept or cut."""
    media, stage2, stage3 = _records(120)
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(target_size=50))
    scored = [e for e in cs.filter_log if e.get("decision") in ("keep", "drop")]
    assert scored, "expected keep/drop entries"
    for e in scored:
        if e.get("reason") in (None, "rank_below_target_size") or e["decision"] == "keep":
            assert "quality_score" in e
            assert "narrative_relevance" in e
            assert "specialness_score" in e


def test_montage_group_detected_for_dense_same_backdrop_burst() -> None:
    """S-2.11.4: 7 same-spot, same-backdrop photos within 30 min → one montage
    group; the per-viewpoint cap exempts them so all survive."""
    media, stage2, stage3 = [], [], []
    for i in range(7):
        ch = f"m{i}"
        # phashes pairwise Hamming 6 (>5 so dedup keeps them; <=14 so montage groups)
        ph = f"{(7 << (3 * i)):016x}"
        media.append(MediaRecord(
            content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo", file_size=1,
            quick_stats={"phash": ph, "dhash": "0"}, gps_lat=36.879, gps_lon=-111.510,
            capture_timestamp=f"2026-04-06T19:0{i}:00", capture_source="exif"))
        stage2.append(Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=0.8,
                                         narrative_relevance_score=0.7, embedding_dim=8))
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(quality_threshold=0.0, target_size=50))
    assert len(cs.montage_groups) == 1
    assert len(cs.montage_groups[0]) >= 6
    assert {it.content_hash for it in cs.items} >= {f"m{i}" for i in range(6)}


def test_no_montage_without_gps_or_too_few() -> None:
    media, stage2, stage3 = [], [], []
    for i in range(7):  # same backdrop, but NO gps → no montage
        ch = f"n{i}"
        ph = f"{(7 << (3 * i)):016x}"
        media.append(MediaRecord(content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo",
                                 file_size=1, quick_stats={"phash": ph, "dhash": "0"},
                                 capture_timestamp=f"2026-04-06T19:0{i}:00", capture_source="exif"))
        stage2.append(Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=0.8,
                                         narrative_relevance_score=0.7, embedding_dim=8))
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(quality_threshold=0.0, target_size=50))
    assert cs.montage_groups == []


def test_viewpoint_candidate_cap_limits_per_gps_cell() -> None:
    """T-2.11.1.6: at most 4 candidates survive per ~1km GPS cell, so the judge
    spreads across places. 8 photos at one overlook → 4 kept; a distinct spot is
    independent; no-GPS exempt."""
    media, stage2, stage3 = [], [], []
    def add(ch, lat, lon, q):
        m = MediaRecord(content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo",
                        file_size=1, quick_stats={"phash": _spread_phash(abs(hash(ch)) % 900), "dhash": "0"},
                        gps_lat=lat, gps_lon=lon)
        media.append(m)
        stage2.append(Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=q,
                                         narrative_relevance_score=0.7, embedding_dim=8))
    for i in range(8):  # 8 at the same overlook
        add(f"hb{i}", 36.879, -111.510, 0.5 + i * 0.05)
    add("zion", 37.2, -112.95, 0.9)  # a distinct viewpoint
    cs = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                   overrides=PreFilterOverrides(quality_threshold=0.0, target_size=50))
    kept = {it.content_hash for it in cs.items}
    hb_kept = sum(1 for k in kept if k.startswith("hb"))
    assert hb_kept == 4  # capped to 4 candidates at the one overlook
    assert "zion" in kept  # distinct spot survives
    capped = [e for e in cs.filter_log if e.get("reason") == "viewpoint_candidate_cap"]
    assert len(capped) == 4  # the other 4 hb shots dropped


def test_short_video_scene_is_ineligible() -> None:
    """S-2.11.1: a video scene under ~2s is a jerky flash — dropped before it
    can win a slot; a >=2s scene from the same video survives."""
    vid = MediaRecord(
        content_hash="vid", source_path="/tmp/vid.mp4", media_type="video", file_size=9,
        quick_stats={"width": 1920, "height": 1080},
        scenes=[
            SceneRecord(index=0, start_seconds=0.0, end_seconds=1.2, representative_frame_paths=[]),
            SceneRecord(index=1, start_seconds=1.2, end_seconds=4.4, representative_frame_paths=[]),
        ],
    )
    stage2 = [
        Stage2AssetOutputs(content_hash="vid", scene_index=0, caption="flash", quality_score=0.9,
                           narrative_relevance_score=0.8, embedding_dim=8),
        Stage2AssetOutputs(content_hash="vid", scene_index=1, caption="clip", quality_score=0.9,
                           narrative_relevance_score=0.8, embedding_dim=8),
    ]
    cs = prefilter(media=[vid], stage2=stage2, stage3=[], target_duration_seconds=10,
                   overrides=PreFilterOverrides(quality_threshold=0.0, target_size=10))
    keys = {it.content_hash + (f"#{it.scene_index}" if it.scene_index is not None else "") for it in cs.items}
    assert "vid#1" in keys
    assert "vid#0" not in keys
    dropped = [e for e in cs.filter_log if e.get("reason") == "video_too_short"]
    assert [e["key"] for e in dropped] == ["vid#0"]


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
