"""Tests for destination mapping + the shared ReservationSet (S-2.10.5)."""

from __future__ import annotations

from dataclasses import dataclass

from impact_crater.pipeline.brief_intent import NamedDestination
from impact_crater.pipeline.destinations import ReservationSet, map_destinations


@dataclass
class _FakeAsset:
    key: str
    caption: str = ""
    location_description: str | None = None
    metadata_summary: str | None = None
    specialness_score: float = 0.5
    quality_score: float = 0.5
    gps_lat: float | None = None
    gps_lon: float | None = None


def test_text_match_reserves_best_per_dest() -> None:
    assets = [
        _FakeAsset("a", caption="the Hoover Dam spillway", specialness_score=0.9),
        _FakeAsset("b", caption="hoover dam from above", specialness_score=0.4),
        _FakeAsset("c", caption="a red canyon", specialness_score=0.8),  # no match
    ]
    dests = [NamedDestination(name="Las Vegas", aliases=["vegas", "hoover dam"])]
    plan, res = map_destinations(assets, dests, per_dest=1)
    d = plan.named_destinations[0]
    assert d.basis == "matched"
    assert d.asset_keys == {"a", "b"}
    assert d.best_keys == ["a"]  # highest specialness reserved
    assert res.keys == frozenset({"a"})
    assert res.reason_by_key["a"] == "dest:Las Vegas"
    assert res.source == "destination"


def test_named_place_with_no_media_is_basis_none() -> None:
    assets = [_FakeAsset("a", caption="a mountain")]
    plan, res = map_destinations(assets, [NamedDestination(name="Paris", aliases=["eiffel"])])
    assert plan.named_destinations[0].basis == "none"
    assert res.keys == frozenset()


def test_reservation_set_merge_prefers_destination_reason() -> None:
    a = ReservationSet(keys=frozenset({"x"}), reason_by_key={"x": "dest:Zion"}, source="destination")
    b = ReservationSet(keys=frozenset({"x", "y"}), reason_by_key={"x": "refine", "y": "refine:more"}, source="refinement")
    merged = a.merged_with(b)
    assert merged.keys == frozenset({"x", "y"})
    assert merged.reason_by_key["x"] == "dest:Zion"  # self (destination) wins
    assert merged.reason_by_key["y"] == "refine:more"


def test_scene_keys_are_preserved() -> None:
    assets = [_FakeAsset("h#2", caption="las vegas strip at night")]
    _, res = map_destinations(assets, [NamedDestination(name="Las Vegas", aliases=["vegas"])], per_dest=2)
    assert "h#2" in res.keys
