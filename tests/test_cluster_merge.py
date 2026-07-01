"""Tests for the cast cluster merge-pass (S-2.10.4)."""

from __future__ import annotations

import numpy as np

from impact_crater.media.cast import (
    FaceObservation,
    _merge_oversplit_clusters,
    build_cast_inventory,
)


def _unit(*vals: float) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / float(np.linalg.norm(v))


def _obs(ch: str, vec: np.ndarray, day: str = "2026-04-05") -> FaceObservation:
    return FaceObservation(
        content_hash=ch, embedding=vec, capture_timestamp=f"{day}T10:00:00",
        location_key="loc", bbox=(0.4, 0.4, 0.2, 0.2),
    )


def test_close_centroids_merge() -> None:
    near_a = _unit(1.0, 0.05, 0.0)
    near_b = _unit(1.0, 0.06, 0.0)  # ~same direction, different photos
    clusters = [[_obs("p1", near_a)], [_obs("p2", near_b)]]
    merged = _merge_oversplit_clusters(clusters, 0.92)
    assert len(merged) == 1
    assert {m.content_hash for m in merged[0]} == {"p1", "p2"}


def test_orthogonal_identities_do_not_merge() -> None:
    clusters = [[_obs("a", _unit(1, 0, 0))], [_obs("b", _unit(0, 1, 0))]]
    merged = _merge_oversplit_clusters(clusters, 0.92)
    assert len(merged) == 2


def test_co_occurrence_guard_prevents_merge() -> None:
    """Two clusters that share a photo are never merged (same person rarely
    appears twice in one frame)."""
    v = _unit(1.0, 0.02, 0.0)
    clusters = [[_obs("shared", v)], [_obs("shared", _unit(1.0, 0.03, 0.0))]]
    merged = _merge_oversplit_clusters(clusters, 0.92)
    assert len(merged) == 2  # not merged despite near-identical centroids


def test_embeddingless_singletons_never_merge() -> None:
    clusters = [[_obs("a", None)], [_obs("b", None)]]  # type: ignore[arg-type]
    assert len(_merge_oversplit_clusters(clusters, 0.5)) == 2


def test_merge_flips_split_member_to_group() -> None:
    """A person split across two clusters, each below the group day-threshold,
    reaches group after merging."""
    va = _unit(1.0, 0.04, 0.0)
    obs = [
        _obs("d1", va, day="2026-04-01"),
        _obs("d2", _unit(1.0, 0.05, 0.0), day="2026-04-02"),
        _obs("d3", _unit(1.0, 0.045, 0.01), day="2026-04-03"),
    ]
    # As three separate single-obs clusters none is a group; merged → one person
    # across 3 days/appearances.
    # cluster_threshold so tight the base clusterer keeps them as 3 singletons;
    # the merge-pass (0.99) then fuses them into one 3-day person → group.
    inv = build_cast_inventory([obs[0], obs[1], obs[2]], cluster_threshold=0.999999,
                               group_min_appearances=3, group_min_days=3, group_min_breadth=3,
                               merge_oversplit=True, cluster_merge_threshold=0.99)
    assert any(p.is_group for p in inv.persons)


def test_merge_off_is_inert() -> None:
    # cos ~0.93 — the base clusterer (0.99) keeps them separate, and with the
    # merge-pass off they stay two distinct persons.
    inv = build_cast_inventory([_obs("a", _unit(1.0, 0.0, 0.0)), _obs("b", _unit(0.93, 0.367, 0.0))],
                               cluster_threshold=0.99, merge_oversplit=False)
    assert len(inv.persons) == 2  # no merge → two clusters
