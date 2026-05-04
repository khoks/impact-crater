"""Stage 4 — deterministic pre-filter per ADR-0011 §"Stage 4 — Pre-filter".

No LLM calls. Inputs: full media set + Stage 2 + Stage 3 outputs +
brief + target_duration. Output: `CandidateSet` sized within the
floor/ceiling envelope.

Floor/ceiling math (per ADR-0011, restated):

    floor   = max(50, ceil(target_duration_seconds * 2))
    ceiling = floor(input_count * 0.80)
    default_target = clamp(ceil(input_count * 0.30), floor, ceiling)
    target_size = clamp(user_override or default_target, floor, ceiling)

Pre-filter steps:
  1. Apply quality floor (drop items with quality_score < threshold).
  2. Dedup clustering via Stage-1 pHash (Hamming ≤ 5).
     Each cluster contributes ⌈cluster_size / dedup_factor⌉ representatives.
  3. Time/location clustering via Stage-3 metadata.
     Clusters > 10 items down-sample to 10 representatives.
  4. Rank by combined_score = α*quality + β*narrative + γ*scene_diversity.
  5. Take top `target_size`.

`filter_log` records every drop/keep decision so the cost-transparency UI
can surface "we dropped 47 photos due to quality floor; 12 due to dedup."
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from impact_crater.llm_clients.base import CandidateRef
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.types import Stage2AssetOutputs, Stage3AssetOutputs


# ---- Public types ------------------------------------------------------


@dataclass
class CandidateSet:
    items: list[CandidateRef]
    cluster_metadata: dict[str, Any]
    filter_log: list[dict[str, Any]]
    target_size: int
    floor: int
    ceiling: int


@dataclass
class PreFilterOverrides:
    quality_threshold: float | None = None  # default 0.4
    dedup_factor: int | None = None         # default 3
    target_size: int | None = None          # user override; clamped to [floor, ceiling]
    weight_quality: float | None = None     # default α=0.3
    weight_narrative: float | None = None   # default β=0.5
    weight_diversity: float | None = None   # default γ=0.2


# ---- Defaults ----------------------------------------------------------


_DEFAULT_QUALITY_THRESHOLD = 0.4
_DEFAULT_DEDUP_FACTOR = 3
_DEFAULT_LOCATION_CLUSTER_CAP = 10
_DEFAULT_PHASH_HAMMING = 5
_DEFAULT_WEIGHTS = (0.3, 0.5, 0.2)  # (quality, narrative, diversity)


# ---- Public API --------------------------------------------------------


def prefilter(
    *,
    media: list[MediaRecord],
    stage2: list[Stage2AssetOutputs],
    stage3: list[Stage3AssetOutputs],
    target_duration_seconds: int,
    overrides: PreFilterOverrides | None = None,
) -> CandidateSet:
    """Run the deterministic Stage 4 pre-filter."""
    overrides = overrides or PreFilterOverrides()
    weights = (
        overrides.weight_quality if overrides.weight_quality is not None else _DEFAULT_WEIGHTS[0],
        overrides.weight_narrative if overrides.weight_narrative is not None else _DEFAULT_WEIGHTS[1],
        overrides.weight_diversity if overrides.weight_diversity is not None else _DEFAULT_WEIGHTS[2],
    )
    quality_threshold = (
        overrides.quality_threshold
        if overrides.quality_threshold is not None
        else _DEFAULT_QUALITY_THRESHOLD
    )
    dedup_factor = overrides.dedup_factor if overrides.dedup_factor is not None else _DEFAULT_DEDUP_FACTOR

    # Build per-asset records: one per photo, one per video scene.
    assets = _join_assets(media, stage2, stage3)
    input_count = len(assets)
    floor, ceiling = compute_envelope(input_count, target_duration_seconds)
    target_size = _resolve_target_size(input_count, floor, ceiling, overrides.target_size)

    filter_log: list[dict[str, Any]] = []

    # Step 1 — quality floor.
    after_quality = _apply_quality_floor(assets, quality_threshold, filter_log)

    # Step 2 — dedup clusters via pHash.
    dedup_clusters = _phash_clusters(after_quality)
    after_dedup = _apply_dedup(after_quality, dedup_clusters, dedup_factor, filter_log)

    # Step 3 — location/time clusters.
    location_clusters = _location_clusters(after_dedup)
    after_location = _cap_location_clusters(
        after_dedup, location_clusters, _DEFAULT_LOCATION_CLUSTER_CAP, filter_log
    )

    # Step 4 — rank by combined score; assign placeholder diversity score
    # from the dedup-cluster size (smaller cluster → higher diversity).
    cluster_size_by_asset = _cluster_size_by_asset(after_location, dedup_clusters)
    ranked = sorted(
        after_location,
        key=lambda a: -_combined_score(a, weights, cluster_size_by_asset.get(a.key, 1)),
    )

    # Step 5 — take top `target_size` (already clamped to [floor, ceiling]).
    chosen = ranked[:target_size]
    for asset in ranked[target_size:]:
        filter_log.append(
            {
                "key": asset.key,
                "decision": "drop",
                "reason": "rank_below_target_size",
            }
        )
    for asset in chosen:
        filter_log.append({"key": asset.key, "decision": "keep"})

    items = [_to_candidate_ref(a) for a in chosen]

    cluster_metadata = {
        "dedup_cluster_count": len(dedup_clusters),
        "location_cluster_count": len(location_clusters),
        "input_count": input_count,
    }
    return CandidateSet(
        items=items,
        cluster_metadata=cluster_metadata,
        filter_log=filter_log,
        target_size=target_size,
        floor=floor,
        ceiling=ceiling,
    )


# ---- Envelope math ----------------------------------------------------


def compute_envelope(
    input_count: int,
    target_duration_seconds: int,
) -> tuple[int, int]:
    """Return (floor, ceiling) per ADR-0011 Stage 4 math.

    Edge cases:
      - input_count < 50 → floor = input_count (pass-through)
      - target_duration_seconds = 0 → floor = max(50, input_count) safely
      - input_count = 0 → (0, 0)
    """
    if input_count <= 0:
        return (0, 0)
    raw_floor = max(50, math.ceil(max(target_duration_seconds, 0) * 2))
    floor = min(raw_floor, input_count)
    ceiling = max(floor, math.floor(input_count * 0.80))
    return (floor, ceiling)


def _resolve_target_size(
    input_count: int,
    floor: int,
    ceiling: int,
    user_override: int | None,
) -> int:
    if input_count == 0:
        return 0
    default_target = max(floor, min(ceiling, math.ceil(input_count * 0.30)))
    if user_override is None:
        return default_target
    return max(floor, min(ceiling, user_override))


# ---- Asset join ------------------------------------------------------


@dataclass
class _Asset:
    """One pre-filter unit: a photo or a video scene."""

    content_hash: str
    scene_index: int | None
    quality_score: float
    narrative_relevance_score: float
    caption: str
    phash_hex: str | None
    location_description: str | None
    time_of_day: str | None
    raw_metadata: dict[str, Any] | None = None
    metadata_summary: str | None = None

    @property
    def key(self) -> str:
        if self.scene_index is None:
            return self.content_hash
        return f"{self.content_hash}#{self.scene_index}"


def _join_assets(
    media: list[MediaRecord],
    stage2: list[Stage2AssetOutputs],
    stage3: list[Stage3AssetOutputs],
) -> list[_Asset]:
    """Index Stage 2/3 outputs by (content_hash, scene_index) and join with Stage 1."""
    s2_by_key = {(o.content_hash, o.scene_index): o for o in stage2}
    s3_by_key = {(o.content_hash, o.scene_index): o for o in stage3}

    out: list[_Asset] = []
    for rec in media:
        if rec.media_type == "photo":
            out.append(_make_asset(rec, None, s2_by_key, s3_by_key))
        elif rec.media_type == "video" and rec.scenes:
            for scene in rec.scenes:
                out.append(_make_asset(rec, scene.index, s2_by_key, s3_by_key))
    return out


def _make_asset(
    rec: MediaRecord,
    scene_index: int | None,
    s2_by_key: dict,
    s3_by_key: dict,
) -> _Asset:
    s2 = s2_by_key.get((rec.content_hash, scene_index))
    s3 = s3_by_key.get((rec.content_hash, scene_index))
    metadata_dict = s3.metadata.model_dump() if s3 else None
    return _Asset(
        content_hash=rec.content_hash,
        scene_index=scene_index,
        quality_score=float(s2.quality_score) if s2 else 0.0,
        narrative_relevance_score=float(s2.narrative_relevance_score) if s2 else 0.0,
        caption=s2.caption if s2 else "",
        phash_hex=str(rec.quick_stats.get("phash") or "") or None,
        location_description=metadata_dict.get("location", {}).get("description") if metadata_dict else None,
        time_of_day=metadata_dict.get("time_of_day") if metadata_dict else None,
        raw_metadata=metadata_dict,
        metadata_summary=_summarize_metadata(metadata_dict) if metadata_dict else None,
    )


def _summarize_metadata(md: dict[str, Any]) -> str:
    """Compact text summary of the rich metadata for the Stage 5 prompt."""
    parts: list[str] = []
    if td := md.get("time_of_day"):
        parts.append(f"time={td}")
    if mood := md.get("mood"):
        parts.append(f"mood={mood}")
    if light := md.get("lighting"):
        parts.append(f"lighting={light}")
    if loc := md.get("location", {}).get("description"):
        parts.append(f"loc={loc}")
    if (people := md.get("people", {}).get("count")) is not None:
        parts.append(f"people={people}")
    if tags := md.get("generic_tags"):
        parts.append(f"tags={','.join(tags[:4])}")
    return " | ".join(parts)


# ---- Filter steps -----------------------------------------------------


def _apply_quality_floor(
    assets: list[_Asset], threshold: float, filter_log: list[dict[str, Any]]
) -> list[_Asset]:
    out = []
    for a in assets:
        if a.quality_score < threshold:
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "quality_below_threshold",
                    "quality_score": a.quality_score,
                    "threshold": threshold,
                }
            )
        else:
            out.append(a)
    return out


def _phash_clusters(assets: list[_Asset]) -> list[list[_Asset]]:
    """Group by perceptual-hash Hamming distance ≤ 5."""
    clusters: list[list[_Asset]] = []
    for a in assets:
        if not a.phash_hex:
            clusters.append([a])
            continue
        placed = False
        for cluster in clusters:
            head = cluster[0]
            if head.phash_hex and _hamming_hex(a.phash_hex, head.phash_hex) <= _DEFAULT_PHASH_HAMMING:
                cluster.append(a)
                placed = True
                break
        if not placed:
            clusters.append([a])
    return clusters


def _hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two hex-encoded perceptual hashes."""
    if len(a) != len(b):
        return max(len(a), len(b)) * 4
    int_a = int(a, 16)
    int_b = int(b, 16)
    return bin(int_a ^ int_b).count("1")


def _apply_dedup(
    assets: list[_Asset],
    clusters: list[list[_Asset]],
    dedup_factor: int,
    filter_log: list[dict[str, Any]],
) -> list[_Asset]:
    keep: set[str] = set()
    for cluster in clusters:
        # Pick best-scoring members; drop the rest.
        cluster_sorted = sorted(
            cluster,
            key=lambda a: -(_combined_score(a, _DEFAULT_WEIGHTS, len(cluster))),
        )
        cap = max(1, math.ceil(len(cluster) / max(dedup_factor, 1)))
        for a in cluster_sorted[:cap]:
            keep.add(a.key)
        for a in cluster_sorted[cap:]:
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "dedup_cluster_excess",
                    "cluster_size": len(cluster),
                    "dedup_factor": dedup_factor,
                }
            )
    return [a for a in assets if a.key in keep]


def _location_clusters(assets: list[_Asset]) -> dict[str, list[_Asset]]:
    """Group by (time_of_day, location_description) — coarse stand-in
    for true GPS clustering until M5 brings full EXIF parsing in."""
    out: dict[str, list[_Asset]] = {}
    for a in assets:
        bucket = f"{a.time_of_day or '_'}|{a.location_description or '_'}"
        out.setdefault(bucket, []).append(a)
    return out


def _cap_location_clusters(
    assets: list[_Asset],
    clusters: dict[str, list[_Asset]],
    cap: int,
    filter_log: list[dict[str, Any]],
) -> list[_Asset]:
    keep: set[str] = set()
    for bucket, members in clusters.items():
        sorted_members = sorted(
            members,
            key=lambda a: -(a.quality_score * 0.5 + a.narrative_relevance_score * 0.5),
        )
        for a in sorted_members[:cap]:
            keep.add(a.key)
        for a in sorted_members[cap:]:
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "location_cluster_excess",
                    "bucket": bucket,
                    "cap": cap,
                }
            )
    return [a for a in assets if a.key in keep]


def _cluster_size_by_asset(
    assets: list[_Asset],
    clusters: list[list[_Asset]],
) -> dict[str, int]:
    out: dict[str, int] = {}
    keys = {a.key for a in assets}
    for cluster in clusters:
        size = len(cluster)
        for a in cluster:
            if a.key in keys:
                out[a.key] = size
    return out


def _combined_score(
    asset: _Asset,
    weights: tuple[float, float, float],
    cluster_size: int,
) -> float:
    α, β, γ = weights
    diversity = 1.0 / max(cluster_size, 1)
    return (
        α * asset.quality_score
        + β * asset.narrative_relevance_score
        + γ * diversity
    )


def _to_candidate_ref(asset: _Asset) -> CandidateRef:
    return CandidateRef(
        content_hash=asset.content_hash,
        scene_index=asset.scene_index,
        caption=asset.caption or None,
        metadata_summary=asset.metadata_summary,
        quality_score=asset.quality_score,
        narrative_relevance=asset.narrative_relevance_score,
    )


# Re-export for callers
__all__ = [
    "CandidateSet",
    "PreFilterOverrides",
    "compute_envelope",
    "prefilter",
]


# Annotations imported for typing but unused at runtime — keep for ruff.
_ = field
