"""Tests for the auto trip cast — clustering, group/crowd, coverage (A-018 / N-012)."""

from __future__ import annotations

import numpy as np
import pytest
from impact_crater.media.cast import (
    FaceObservation,
    build_cast_inventory,
    compute_coverage,
    location_key,
)
from impact_crater.media.face_embed import (
    GeminiFaceEmbedder,
    InsightFaceEmbedder,
    build_face_embedder,
)


def _unit(*vals: float) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


# Three distinguishable identity vectors (orthogonal → cosine 0).
ALICE = _unit(1, 0, 0, 0)
BOB = _unit(0, 1, 0, 0)
GUIDE = _unit(0, 0, 1, 0)


def _obs(emb, ch, ts, loc) -> FaceObservation:
    return FaceObservation(content_hash=ch, embedding=emb, capture_timestamp=ts, location_key=loc, bbox=(0, 0, 1, 1))


# ---- Clustering + group/crowd ------------------------------------------


def test_group_vs_crowd_by_recurrence_breadth() -> None:
    """Alice + Bob recur across days AND locations → group. The guide
    appears many times but only at ONE place/day → crowd (N-012)."""
    obs = [
        # Alice: 3 days, 3 locations → broad
        _obs(ALICE, "p1", "2026-04-05T09:00:00", "37.21,-112.94"),
        _obs(ALICE, "p2", "2026-04-06T10:00:00", "37.30,-113.00"),
        _obs(ALICE, "p3", "2026-04-07T11:00:00", "37.25,-112.50"),
        # Bob: same trip footprint
        _obs(BOB, "p1", "2026-04-05T09:00:00", "37.21,-112.94"),
        _obs(BOB, "p2", "2026-04-06T10:00:00", "37.30,-113.00"),
        _obs(BOB, "p3", "2026-04-07T11:00:00", "37.25,-112.50"),
        # Guide: 5 appearances, all one day + one location → narrow
        *[_obs(GUIDE, f"g{i}", "2026-04-05T09:00:00", "37.21,-112.94") for i in range(5)],
    ]
    inv = build_cast_inventory(obs, cluster_threshold=0.5, group_min_breadth=3)
    groups = {p.person_id for p in inv.group}
    # Exactly two group people; the guide (most appearances) is crowd.
    assert len(inv.group) == 2
    assert len(inv.crowd) == 1
    guide = inv.crowd[0]
    assert guide.appearance_count == 5
    assert guide.distinct_days == 1
    assert guide.distinct_locations == 1
    # Group members tracked per photo for the curation annotation.
    assert set(inv.group_persons_by_hash.get("p1", [])) == groups


def test_two_appearances_is_not_group_even_when_breadth_high() -> None:
    """A face seen only twice — even across two different days AND places
    (breadth 4) — is a passing stranger / detection false positive, not the
    travel party. Regression for the real SW-trip job where 81 people were
    tagged 'group'; min appearances + min distinct days demote these."""
    obs = [
        _obs(ALICE, "p1", "2026-04-05T09:00:00", "37.21,-112.94"),
        _obs(ALICE, "p2", "2026-04-06T10:00:00", "37.30,-113.00"),
    ]
    inv = build_cast_inventory(obs, cluster_threshold=0.5)
    assert len(inv.persons) == 1
    p = inv.persons[0]
    assert p.appearance_count == 2
    assert p.recurrence_breadth == 4  # 2 days + 2 locations
    assert not p.is_group  # demoted: too few appearances


def test_many_appearances_one_day_is_not_group() -> None:
    """Many appearances spread over several LOCATIONS but all on ONE day is
    the day-tour-companion case — should stay crowd (requires >=2 days)."""
    obs = [
        _obs(BOB, f"b{i}", "2026-04-05T09:00:00", f"37.2{i},-112.9{i}")
        for i in range(5)
    ]
    inv = build_cast_inventory(obs, cluster_threshold=0.5)
    p = inv.persons[0]
    assert p.appearance_count == 5
    assert p.distinct_days == 1
    assert not p.is_group


def test_faces_without_embedding_become_singletons() -> None:
    obs = [
        _obs(None, "a", "2026-04-05T09:00:00", "loc1"),
        _obs(None, "b", "2026-04-05T09:00:00", "loc1"),
    ]
    inv = build_cast_inventory(obs, cluster_threshold=0.5)
    # Two unidentifiable faces → two singleton persons, neither group.
    assert len(inv.persons) == 2
    assert all(not p.is_group for p in inv.persons)


def test_same_person_across_outfits_clusters_when_similar() -> None:
    near = _unit(0.97, 0.24, 0, 0)  # cosine ~0.97 with ALICE
    obs = [
        _obs(ALICE, "p1", "2026-04-05T09:00:00", "loc1"),
        _obs(near, "p2", "2026-04-06T09:00:00", "loc2"),
        _obs(ALICE, "p3", "2026-04-07T09:00:00", "loc3"),
    ]
    inv = build_cast_inventory(obs, cluster_threshold=0.8, group_min_breadth=3)
    assert len(inv.persons) == 1
    assert inv.persons[0].is_group


# ---- Coverage ----------------------------------------------------------


def test_coverage_flags_missing_group_member() -> None:
    obs = [
        _obs(ALICE, "p1", "2026-04-05T09:00:00", "l1"),
        _obs(ALICE, "p2", "2026-04-06T09:00:00", "l2"),
        _obs(ALICE, "p3", "2026-04-07T09:00:00", "l3"),
        _obs(BOB, "b1", "2026-04-05T09:00:00", "l1"),
        _obs(BOB, "b2", "2026-04-06T09:00:00", "l2"),
        _obs(BOB, "b3", "2026-04-07T09:00:00", "l3"),
    ]
    inv = build_cast_inventory(obs, cluster_threshold=0.5, group_min_breadth=3)
    alice = next(p for p in inv.group if "p1" in p.content_hashes)
    bob = next(p for p in inv.group if "b1" in p.content_hashes)
    # Selection includes only Alice's photos → Bob is flagged missing.
    report = compute_coverage(inv, {"p1", "p2"})
    assert alice.person_id in report.covered_person_ids
    assert bob.person_id in report.missing_person_ids
    assert not report.fully_covered

    full = compute_coverage(inv, {"p1", "b1"})
    assert full.fully_covered


# ---- location_key + embedder factory -----------------------------------


def test_location_key_prefers_gps_then_description() -> None:
    assert location_key(37.2982, -113.0263, "Zion") == "37.3,-113.03"
    assert location_key(None, None, "Bryce Canyon Overlook") == "bryce canyon overlook"
    assert location_key(None, None, None) is None


def test_build_face_embedder_defaults_to_gemini() -> None:
    assert isinstance(build_face_embedder(None, router=object()), GeminiFaceEmbedder)
    assert isinstance(build_face_embedder("gemini", router=object()), GeminiFaceEmbedder)
    assert isinstance(build_face_embedder("insightface", router=object()), InsightFaceEmbedder)
    # Unknown backend falls back to the default.
    assert isinstance(build_face_embedder("nonsense", router=object()), GeminiFaceEmbedder)


async def test_gemini_embedder_calls_router_and_normalizes() -> None:
    class FakeRouter:
        async def embed_image(self, crop: bytes, *, content_hash: str) -> np.ndarray:
            return np.array([3.0, 4.0], dtype=np.float32)  # norm 5 → unit (0.6, 0.8)

    emb = GeminiFaceEmbedder(FakeRouter())
    out = await emb.embed_face_crops([b"crop1", b""])  # empty crop → None
    assert out[1] is None
    assert out[0] == pytest.approx(np.array([0.6, 0.8]), abs=1e-5)
