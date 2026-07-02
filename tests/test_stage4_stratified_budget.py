"""Tests for the capture-day stratified Stage-4 budget (S-2.10.6, A/B-gated)."""

from __future__ import annotations

from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.stage4_prefilter import (
    PreFilterOverrides,
    _stratified_take,
    prefilter,
)
from impact_crater.pipeline.types import RichMetadataPhoto, Stage2AssetOutputs, Stage3AssetOutputs


class _A:
    def __init__(self, key: str, ts: str) -> None:
        self.key = key
        self.capture_timestamp = ts


def test_stratified_take_gives_each_day_a_floor() -> None:
    # Day 1 has 10 high-rankers, day 5 has 2 low-rankers (already rank-sorted).
    ranked = [_A(f"d1-{i}", "2026-04-01T10:00:00") for i in range(10)]
    ranked += [_A("d5-0", "2026-04-05T10:00:00"), _A("d5-1", "2026-04-05T11:00:00")]
    chosen = _stratified_take(ranked, budget=6, min_per_day=3)
    keys = {a.key for a in chosen}
    assert len(chosen) == 6
    assert "d5-0" in keys and "d5-1" in keys  # day 5 reps that a global top-6 would starve


def test_stratified_take_sums_to_budget_and_preserves_order() -> None:
    ranked = [_A(f"x{i}", f"2026-04-0{(i % 3) + 1}T10:00:00") for i in range(9)]
    chosen = _stratified_take(ranked, budget=5, min_per_day=1)
    assert len(chosen) == 5
    # output preserves the input rank order
    idx = [ranked.index(a) for a in chosen]
    assert idx == sorted(idx)


def test_stratified_take_zero_budget() -> None:
    assert _stratified_take([_A("a", "2026-04-01T10:00:00")], 0, 3) == []


def _photo(ch: str, day: str, q: float, idx: int):
    from tests.test_stage4_prefilter import _spread_phash
    # Deterministic pHash spread — hash(str) is salted per process and could
    # collide two assets within the dedup Hamming radius on some seeds.
    media = MediaRecord(content_hash=ch, source_path=f"/tmp/{ch}.jpg", media_type="photo",
                        file_size=1, quick_stats={"phash": _spread_phash(idx), "dhash": "00"},
                        capture_timestamp=f"{day}T10:00:00")
    s2 = Stage2AssetOutputs(content_hash=ch, caption=ch, quality_score=q,
                            narrative_relevance_score=0.5, embedding_dim=8)
    # Unique location per shot → uniform diversity, so quality alone decides rank.
    s3 = Stage3AssetOutputs(content_hash=ch, metadata=RichMetadataPhoto(time_of_day="midday",
                            location={"description": f"loc-{ch}"}))
    return media, s2, s3


def test_stratified_flag_gives_late_days_representation() -> None:
    # 60 sharp day-1 shots + 10 low-quality day-5 shots; input>63 so the envelope
    # floor (50) is the target and the global top-50 is all day-1.
    media, stage2, stage3 = [], [], []
    for i in range(70):
        day = "2026-04-01" if i < 60 else "2026-04-05"
        q = 0.9 if i < 60 else 0.5  # day-5 survives the floor but ranks last
        m, s2, s3 = _photo(f"h{i:02d}", day, q, i)
        media.append(m); stage2.append(s2); stage3.append(s3)
    base = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10)
    strat = prefilter(media=media, stage2=stage2, stage3=stage3, target_duration_seconds=10,
                      overrides=PreFilterOverrides(stratify_by_capture_day=True, stratified_min_per_day=2))
    day5 = {f"h{i:02d}" for i in range(60, 70)}
    assert not ({it.content_hash for it in base.items} & day5)  # global top-K starved day 5
    assert {it.content_hash for it in strat.items} & day5  # stratified gave day 5 representation
    assert any(e.get("reason") == "stratified_day_budget" for e in strat.filter_log)
