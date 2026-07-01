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
  4. Rank by combined_score = α*quality + β*narrative + δ*specialness +
     γ*scene_diversity (S-2.10.2: specialness participates in ranking and every
     tie-break; a high-specialness shot is also rescued past the quality floor).
  5. Take top `target_size`.

`filter_log` records every drop/keep decision so the cost-transparency UI
can surface "we dropped 47 photos due to quality floor; 12 due to dedup."
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from impact_crater.llm_clients.base import CandidateRef
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.types import Stage2AssetOutputs, Stage3AssetOutputs

log = logging.getLogger(__name__)


# ---- Public types ------------------------------------------------------


@dataclass
class CandidateSet:
    items: list[CandidateRef]
    cluster_metadata: dict[str, Any]
    filter_log: list[dict[str, Any]]
    target_size: int
    floor: int
    ceiling: int
    # S-2.11.4: dense same-backdrop bursts (each = ordered member asset.keys) that
    # Stage 6 can collapse into one rapid burst-montage clip. Empty when none.
    montage_groups: list[list[str]] = field(default_factory=list)


@dataclass
class PreFilterOverrides:
    quality_threshold: float | None = None  # default 0.4
    dedup_factor: int | None = None         # default 3
    target_size: int | None = None          # user override; clamped to [floor, ceiling]
    weight_quality: float | None = None     # default α=0.25
    weight_narrative: float | None = None   # default β=0.40
    weight_specialness: float | None = None  # default δ=0.20 (S-2.10.2)
    weight_diversity: float | None = None   # default γ=0.15
    # S-2.10.2: a genuinely memorable shot (high Stage-3 specialness) survives the
    # quality floor even when slightly soft. None → default 0.75; raise to 1.1
    # to disable the rescue.
    specialness_rescue_threshold: float | None = None
    # A-017 best-of-burst semantic dedup. Cosine ≥ threshold within the
    # time window collapses retakes to their best member. None → defaults;
    # set threshold to 1.1 (impossible) to disable.
    semantic_dedup_threshold: float | None = None      # default 0.93
    semantic_dedup_window_seconds: int | None = None   # default 120
    # S-2.11.4 burst-montage detection knobs. montage_enabled=False is a kill
    # switch (no montage groups ever produced).
    montage_enabled: bool | None = None                # default True
    montage_min_members: int | None = None             # default 6
    montage_window_seconds: int | None = None          # default 1800
    montage_phash_hamming: int | None = None           # default 14


# ---- Defaults ----------------------------------------------------------


_DEFAULT_QUALITY_THRESHOLD = 0.4
_DEFAULT_DEDUP_FACTOR = 3
_DEFAULT_LOCATION_CLUSTER_CAP = 10
_DEFAULT_PHASH_HAMMING = 5
# (quality, narrative, specialness, diversity). S-2.10.2: specialness (the richest
# Stage-3 signal) now participates in ranking + every tie-break so the most
# memorable member of a burst is the one kept and standout shots aren't ranked
# out by bland-but-sharp ones. Narrative stays dominant so the brief still steers.
_DEFAULT_WEIGHTS = (0.25, 0.40, 0.20, 0.15)
_DEFAULT_SPECIALNESS_RESCUE_THRESHOLD = 0.75
# A video scene shorter than this is ineligible (S-2.11.1): <2s of footage in
# the output reads as a jerky flash, so it shouldn't compete for a slot at all.
_DEFAULT_MIN_VIDEO_MS = 2000.0
# T-2.11.1.6: cap candidates per ~1km GPS cell so the judge can't over-pick one
# viewpoint and must fill the target from breadth (it then reaches the full
# duration across many places instead of being trimmed by the Stage-6 cap).
# Slightly above the Stage-6 hard cap (3) so the judge has a best-of choice.
_DEFAULT_VIEWPOINT_CANDIDATE_CAP = 4
_VIEWPOINT_CELL_DP = 2  # round GPS to 2dp ≈ 1.1km
# S-2.11.4 burst-montage: a dense same-backdrop cluster (one GPS cell, short
# window, near-identical framing, many photos) becomes a rapid 0.5s-per-photo
# montage. Used sparingly — needs >=6 such photos.
_DEFAULT_MONTAGE_MIN_MEMBERS = 6
_DEFAULT_MONTAGE_WINDOW_S = 1800  # 30 min
_DEFAULT_MONTAGE_PHASH_HAMMING = 14  # looser than dedup's 5 = "same backdrop"
# A-017 best-of-burst: cosine ≥ this collapses retakes. Within the time
# window we trust a moderate threshold; without timestamps we demand a
# higher one (near-identical visuals) so different scenery never merges.
_DEFAULT_SEMANTIC_DEDUP_THRESHOLD = 0.93
_DEFAULT_SEMANTIC_DEDUP_WINDOW_S = 120
_SEMANTIC_DEDUP_NO_TIME_THRESHOLD = 0.97


# ---- Public API --------------------------------------------------------


def prefilter(
    *,
    media: list[MediaRecord],
    stage2: list[Stage2AssetOutputs],
    stage3: list[Stage3AssetOutputs],
    target_duration_seconds: int,
    overrides: PreFilterOverrides | None = None,
    cast: Any = None,
) -> CandidateSet:
    """Run the deterministic Stage 4 pre-filter.

    `cast` (optional A-018 CastInventory): when present, each asset's
    metadata summary is annotated with the group members visible in it so
    the Stage 5 judge can curate cast-aware ("don't leave anyone out").
    """
    overrides = overrides or PreFilterOverrides()
    weights = (
        overrides.weight_quality if overrides.weight_quality is not None else _DEFAULT_WEIGHTS[0],
        overrides.weight_narrative if overrides.weight_narrative is not None else _DEFAULT_WEIGHTS[1],
        overrides.weight_specialness if overrides.weight_specialness is not None else _DEFAULT_WEIGHTS[2],
        overrides.weight_diversity if overrides.weight_diversity is not None else _DEFAULT_WEIGHTS[3],
    )
    rescue_threshold = (
        overrides.specialness_rescue_threshold
        if overrides.specialness_rescue_threshold is not None
        else _DEFAULT_SPECIALNESS_RESCUE_THRESHOLD
    )
    quality_threshold = (
        overrides.quality_threshold
        if overrides.quality_threshold is not None
        else _DEFAULT_QUALITY_THRESHOLD
    )
    dedup_factor = overrides.dedup_factor if overrides.dedup_factor is not None else _DEFAULT_DEDUP_FACTOR
    semantic_threshold = (
        overrides.semantic_dedup_threshold
        if overrides.semantic_dedup_threshold is not None
        else _DEFAULT_SEMANTIC_DEDUP_THRESHOLD
    )
    semantic_window_s = (
        overrides.semantic_dedup_window_seconds
        if overrides.semantic_dedup_window_seconds is not None
        else _DEFAULT_SEMANTIC_DEDUP_WINDOW_S
    )

    # Build per-asset records: one per photo, one per video scene.
    assets = _join_assets(media, stage2, stage3)
    if cast is not None:
        _annotate_cast(assets, cast)
    input_count = len(assets)
    floor, ceiling = compute_envelope(input_count, target_duration_seconds)
    target_size = _resolve_target_size(input_count, floor, ceiling, overrides.target_size)

    filter_log: list[dict[str, Any]] = []

    # Step 0 — safety floor (A-022). Drop explicit frames before anything
    # else so they can never reach a shareable artifact. "mild" survives;
    # only "explicit" is removed.
    after_safety = _apply_safety_floor(assets, filter_log)

    # Step 0b — min-video floor (S-2.11.1). A video scene under ~2s is a jerky
    # flash in the output; make it ineligible before it can win a slot.
    after_safety = _apply_min_video_floor(after_safety, _DEFAULT_MIN_VIDEO_MS, filter_log)

    # Step 1 — quality floor (with S-2.10.2 specialness rescue).
    after_quality = _apply_quality_floor(
        after_safety, quality_threshold, rescue_threshold, filter_log
    )

    # Step 2 — dedup clusters via pHash (near-identical pixels).
    dedup_clusters = _phash_clusters(after_quality)
    after_dedup = _apply_dedup(after_quality, dedup_clusters, dedup_factor, weights, filter_log)

    # Step 2b — semantic best-of-burst dedup (A-017): collapse retakes of
    # the same moment (same pose/scene from a slightly different angle)
    # that pHash misses, using the embedding + the capture timeline.
    after_semantic = _apply_semantic_dedup(
        after_dedup, weights, semantic_threshold, semantic_window_s, filter_log
    )

    # Step 3 — location/time clusters.
    location_clusters = _location_clusters(after_semantic)
    after_location = _cap_location_clusters(
        after_semantic, location_clusters, _DEFAULT_LOCATION_CLUSTER_CAP, weights, filter_log
    )

    # Step 3a — detect dense same-backdrop bursts (S-2.11.4) BEFORE the
    # per-viewpoint cap, so a >=6-photo burst is found (the cap keeps only 4).
    montage_enabled = overrides.montage_enabled if overrides.montage_enabled is not None else True
    montage_groups: list[list[str]] = []
    if montage_enabled:
        montage_groups = _detect_montage_groups(
            after_location,
            min_members=overrides.montage_min_members or _DEFAULT_MONTAGE_MIN_MEMBERS,
            window_s=overrides.montage_window_seconds or _DEFAULT_MONTAGE_WINDOW_S,
            phash_hamming=overrides.montage_phash_hamming or _DEFAULT_MONTAGE_PHASH_HAMMING,
            filter_log=filter_log,
        )
    montage_member_keys = {k for g in montage_groups for k in g}

    # Step 3b — per-viewpoint candidate cap (T-2.11.1.6): keep at most N best
    # per ~1km GPS cell so the judge spreads across places and fills the target.
    # Montage members are EXEMPT (the montage represents the whole dense burst).
    after_location = _cap_gps_viewpoints(
        after_location, _DEFAULT_VIEWPOINT_CANDIDATE_CAP, weights, filter_log,
        exempt_keys=montage_member_keys,
    )

    # Step 4 — rank by combined score; assign placeholder diversity score
    # from the dedup-cluster size (smaller cluster → higher diversity).
    cluster_size_by_asset = _cluster_size_by_asset(after_location, dedup_clusters)
    ranked = sorted(
        after_location,
        key=lambda a: (-_combined_score(a, weights, cluster_size_by_asset.get(a.key, 1)), a.key),
    )

    # Step 5 — take top `target_size` (already clamped to [floor, ceiling]).
    chosen = ranked[:target_size]
    for asset in ranked[target_size:]:
        filter_log.append(
            {
                "key": asset.key,
                "decision": "drop",
                "reason": "rank_below_target_size",
                **_scores(asset),
            }
        )
    for asset in chosen:
        filter_log.append({"key": asset.key, "decision": "keep", **_scores(asset)})

    items = [_to_candidate_ref(a) for a in chosen]

    # Keep only montage groups whose members all survived into `chosen` and
    # still meet the minimum (S-2.11.4); otherwise those photos render solo.
    chosen_keys = {a.key for a in chosen}
    _min_m = overrides.montage_min_members or _DEFAULT_MONTAGE_MIN_MEMBERS
    montage_groups = [[k for k in g if k in chosen_keys] for g in montage_groups]
    montage_groups = [g for g in montage_groups if len(g) >= _min_m]

    cluster_metadata = {
        "dedup_cluster_count": len(dedup_clusters),
        "location_cluster_count": len(location_clusters),
        "input_count": input_count,
        "montage_group_count": len(montage_groups),
    }

    if not after_quality:
        log.warning(
            "stage4_quality_floor_dropped_all input_count=%d quality_threshold=%.2f",
            input_count,
            quality_threshold,
        )
    log.info(
        "stage4_prefilter_done input_count=%d kept=%d floor=%d ceiling=%d "
        "target_size=%d quality_threshold=%.2f dedup_factor=%d "
        "dedup_clusters=%d location_clusters=%d",
        input_count,
        len(chosen),
        floor,
        ceiling,
        target_size,
        quality_threshold,
        dedup_factor,
        len(dedup_clusters),
        len(location_clusters),
    )

    # Fail-fast if we'd hand zero candidates to Stage 5. Real cost
    # 2026-05-07: a vague brief + cached low quality scores dropped all
    # 36 candidates here, but the pipeline still ran Stage 5 (Tier-L
    # Opus, ~$0.50) before Stage 6 finally raised. With this guard the
    # job fails with a clear, cheap, actionable message before any
    # remote LLM call is wasted on an empty arc judgment.
    if input_count > 0 and not chosen:
        quality_scores = [a.quality_score for a in assets]
        raise Stage4EmptyCandidateSet(
            input_count=input_count,
            quality_threshold=quality_threshold,
            after_quality_count=len(after_quality),
            after_dedup_count=len(after_dedup),
            after_location_count=len(after_location),
            max_quality_score=max(quality_scores),
            min_quality_score=min(quality_scores),
        )

    return CandidateSet(
        items=items,
        cluster_metadata=cluster_metadata,
        filter_log=filter_log,
        target_size=target_size,
        floor=floor,
        ceiling=ceiling,
        montage_groups=montage_groups,
    )


class Stage4EmptyCandidateSet(RuntimeError):
    """Raised when Stage 4's pre-filter eliminates every asset, so Stage 5
    would have nothing to judge. Carries the funnel stats so the
    runner_glue catch can surface an actionable failure_reason."""

    def __init__(
        self,
        *,
        input_count: int,
        quality_threshold: float,
        after_quality_count: int,
        after_dedup_count: int,
        after_location_count: int,
        max_quality_score: float = 0.0,
        min_quality_score: float = 0.0,
    ) -> None:
        self.input_count = input_count
        self.quality_threshold = quality_threshold
        self.after_quality_count = after_quality_count
        self.after_dedup_count = after_dedup_count
        self.after_location_count = after_location_count
        self.max_quality_score = max_quality_score
        self.min_quality_score = min_quality_score
        # The quality-score range disambiguates failure modes at a glance:
        # max=0.00 means scores never joined (Stage 2 failed or key
        # mismatch); a plausible nonzero range means the photos genuinely
        # scored below the floor.
        reason = (
            f"stage4_empty_candidate_set input={input_count} "
            f"after_quality_floor({quality_threshold:.2f})={after_quality_count} "
            f"after_dedup={after_dedup_count} "
            f"after_location={after_location_count} "
            f"quality_score_range=[{min_quality_score:.2f}, {max_quality_score:.2f}]. "
        )
        if max_quality_score <= 0.0:
            reason += (
                "Every asset has quality_score=0.0, which means Stage 2 "
                "scores never attached to these assets — this is an app "
                "bug or a systemic scoring failure, not a media-quality "
                "problem. Check the server logs for stage2 errors."
            )
        else:
            reason += (
                "Likely cause: vague brief produced low narrative-relevance "
                "scores and/or the source folder's photos all score below "
                "the quality threshold. Try a more specific brief or "
                "different media."
            )
        super().__init__(reason)


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
    # A-021 chronology + A-022 enrichment used by the filter + the judge.
    capture_timestamp: str | None = None
    capture_source: str | None = None
    safety_level: str = "safe"
    specialness_score: float = 0.5
    obstruction_level: float = 0.0
    embedding: Any = None  # numpy ndarray for semantic dedup (A-017)
    burst_best_of: int = 1  # how many retakes this asset represents
    scene_duration_ms: float = 0.0  # video-scene natural length (S-2.11.1); 0 for photos
    gps_lat: float | None = None  # T-2.11.1.6 per-viewpoint balance
    gps_lon: float | None = None

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
                out.append(_make_asset(rec, scene.index, s2_by_key, s3_by_key, scene=scene))
    return out


def _make_asset(
    rec: MediaRecord,
    scene_index: int | None,
    s2_by_key: dict,
    s3_by_key: dict,
    *,
    scene: Any = None,
) -> _Asset:
    s2 = s2_by_key.get((rec.content_hash, scene_index))
    s3 = s3_by_key.get((rec.content_hash, scene_index))
    metadata_dict = s3.metadata.model_dump() if s3 else None
    scene_duration_ms = (
        max((scene.end_seconds - scene.start_seconds) * 1000.0, 0.0) if scene is not None else 0.0
    )
    return _Asset(
        content_hash=rec.content_hash,
        scene_index=scene_index,
        scene_duration_ms=scene_duration_ms,
        quality_score=float(s2.quality_score) if s2 else 0.0,
        narrative_relevance_score=float(s2.narrative_relevance_score) if s2 else 0.0,
        caption=s2.caption if s2 else "",
        phash_hex=str(rec.quick_stats.get("phash") or "") or None,
        location_description=metadata_dict.get("location", {}).get("description") if metadata_dict else None,
        time_of_day=metadata_dict.get("time_of_day") if metadata_dict else None,
        raw_metadata=metadata_dict,
        metadata_summary=_summarize_metadata(metadata_dict) if metadata_dict else None,
        capture_timestamp=rec.capture_timestamp,
        capture_source=rec.capture_source,
        safety_level=str(metadata_dict.get("safety_level", "safe")) if metadata_dict else "safe",
        specialness_score=float(metadata_dict.get("specialness_score", 0.5)) if metadata_dict else 0.5,
        obstruction_level=float(metadata_dict.get("obstruction_level", 0.0)) if metadata_dict else 0.0,
        embedding=getattr(s2, "embedding", None) if s2 else None,
        gps_lat=rec.gps_lat,
        gps_lon=rec.gps_lon,
    )


def _annotate_cast(assets: list[_Asset], cast: Any) -> None:
    """Append `cast=[P1,P2]` (group members present) to each asset's
    metadata summary so the Stage 5 judge curates cast-aware (A-018)."""
    by_hash = getattr(cast, "group_persons_by_hash", None)
    if not by_hash:
        return
    for a in assets:
        pids = by_hash.get(a.content_hash)
        if not pids:
            continue
        tag = f"cast={','.join(pids)}"
        a.metadata_summary = f"{a.metadata_summary} | {tag}" if a.metadata_summary else tag


def _summarize_metadata(md: dict[str, Any]) -> str:
    """Compact text summary of the rich metadata for the Stage 5 prompt.

    Surfaces the A-022 enrichment fields (shot type, main-subject
    expressions, specialness, obstructions) so the narrative judge can
    vary framing, find emotional peaks, and avoid blocked shots.
    """
    parts: list[str] = []
    if st := md.get("shot_type"):
        if st != "ambiguous":
            parts.append(f"shot={st}")
    if td := md.get("time_of_day"):
        parts.append(f"time={td}")
    if mood := md.get("mood"):
        parts.append(f"mood={mood}")
    subjects = md.get("main_subjects") or []
    if subjects:
        faces = "; ".join(
            f"{s.get('descriptor', '')}:{s.get('expression', '')}".strip(":")
            for s in subjects[:3]
            if s.get("descriptor") or s.get("expression")
        )
        if faces:
            parts.append(f"subjects=[{faces}]")
    if other := md.get("other_people"):
        parts.append(f"others={other}")
    if light := md.get("lighting"):
        parts.append(f"lighting={light}")
    if scenery := md.get("scenery_description"):
        parts.append(f"scenery={scenery}")
    # Video scenes carry a scene_summary over the 3 sampled frames — surface it
    # so the judge reads what MOVES in the clip, not just one frozen frame (F2).
    if ss := md.get("scene_summary"):
        parts.append(f"motion_summary={ss}")
    if loc := md.get("location", {}).get("description"):
        parts.append(f"loc={loc}")
    spec = md.get("specialness_score")
    if isinstance(spec, (int, float)) and spec >= 0.7:
        parts.append(f"special={spec:.2f}")
    obs = md.get("obstruction_level")
    if isinstance(obs, (int, float)) and obs >= 0.3:
        note = md.get("obstruction_notes") or "obstructed"
        parts.append(f"obstruction={obs:.2f}({note})")
    if tags := md.get("generic_tags"):
        parts.append(f"tags={','.join(tags[:4])}")
    return " | ".join(parts)


# ---- Filter steps -----------------------------------------------------


def _apply_safety_floor(
    assets: list[_Asset], filter_log: list[dict[str, Any]]
) -> list[_Asset]:
    out = []
    for a in assets:
        if a.safety_level == "explicit":
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "safety_explicit",
                    "safety_level": a.safety_level,
                }
            )
        else:
            out.append(a)
    return out


def _apply_min_video_floor(
    assets: list[_Asset], min_ms: float, filter_log: list[dict[str, Any]]
) -> list[_Asset]:
    """Drop video scenes whose natural length is under `min_ms` (S-2.11.1).
    Photos (scene_duration_ms == 0) and timing-less scenes always pass."""
    out = []
    for a in assets:
        if a.scene_index is not None and 0.0 < a.scene_duration_ms < min_ms:
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "video_too_short",
                    "scene_duration_ms": a.scene_duration_ms,
                    "min_ms": min_ms,
                    **_scores(a),
                }
            )
        else:
            out.append(a)
    return out


def _apply_quality_floor(
    assets: list[_Asset],
    threshold: float,
    rescue_threshold: float,
    filter_log: list[dict[str, Any]],
) -> list[_Asset]:
    """Drop low-quality assets — but rescue a genuinely memorable one (S-2.10.2):
    a soft shot with high Stage-3 specialness (a once-in-a-trip moment) is worth
    keeping over a sharp-but-bland frame the floor would otherwise let through."""
    out = []
    for a in assets:
        if a.quality_score >= threshold:
            out.append(a)
        elif a.specialness_score >= rescue_threshold:
            out.append(a)
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "keep",
                    "reason": "specialness_rescue",
                    "quality_score": a.quality_score,
                    "specialness_score": a.specialness_score,
                }
            )
        else:
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "quality_below_threshold",
                    "quality_score": a.quality_score,
                    "threshold": threshold,
                }
            )
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
    weights: tuple[float, float, float, float],
    filter_log: list[dict[str, Any]],
) -> list[_Asset]:
    keep: set[str] = set()
    for cluster in clusters:
        # Pick best-scoring members; drop the rest. Specialness participates
        # via _combined_score (S-2.10.2), so the most memorable retake is kept.
        cluster_sorted = sorted(
            cluster,
            key=lambda a: (-_combined_score(a, weights, len(cluster)), a.key),
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
                    **_scores(a),
                }
            )
    return [a for a in assets if a.key in keep]


def _apply_semantic_dedup(
    assets: list[_Asset],
    weights: tuple[float, float, float],
    threshold: float,
    window_seconds: int,
    filter_log: list[dict[str, Any]],
) -> list[_Asset]:
    """Collapse retakes-of-the-same-moment to their best member (A-017).

    Greedy single-pass clustering: an asset joins the first existing
    cluster whose representative is both visually similar (cosine ≥
    threshold) and close in capture time (≤ window). Assets without an
    embedding are never clustered (pHash already handled exact dupes).
    When BOTH assets carry timestamps the moderate threshold applies;
    when a timestamp is missing we demand near-identical visuals so two
    different scenes from across a trip never merge.
    """
    import numpy as np

    clusters: list[list[_Asset]] = []
    reps: list[np.ndarray] = []
    for a in assets:
        vec = _unit_vector(a.embedding)
        if vec is None:
            clusters.append([a])
            reps.append(None)  # type: ignore[arg-type]
            continue
        placed = False
        for ci, rep in enumerate(reps):
            if rep is None:
                continue
            head = clusters[ci][0]
            cos = float(np.dot(vec, rep))
            both_timed = a.capture_timestamp and head.capture_timestamp
            eff_threshold = threshold if both_timed else max(threshold, _SEMANTIC_DEDUP_NO_TIME_THRESHOLD)
            if cos < eff_threshold:
                continue
            if both_timed and not _within_window(a, head, window_seconds):
                continue
            clusters[ci].append(a)
            placed = True
            break
        if not placed:
            clusters.append([a])
            reps.append(vec)

    kept: list[_Asset] = []
    for cluster in clusters:
        if len(cluster) == 1:
            kept.append(cluster[0])
            continue
        ranked = sorted(
            cluster,
            key=lambda a: -_combined_score(a, weights, 1),
        )
        best = ranked[0]
        best.burst_best_of = len(cluster)
        kept.append(best)
        for loser in ranked[1:]:
            filter_log.append(
                {
                    "key": loser.key,
                    "decision": "drop",
                    "reason": "semantic_duplicate",
                    "kept_key": best.key,
                    "cluster_size": len(cluster),
                    **_scores(loser),
                }
            )
    return kept


def _unit_vector(embedding: Any) -> Any:
    """L2-normalize an embedding to a unit vector, or None if unusable."""
    if embedding is None:
        return None
    import numpy as np

    vec = np.asarray(embedding, dtype=np.float32).ravel()
    if vec.size == 0:
        return None
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return None
    return vec / norm


def _within_window(a: _Asset, b: _Asset, window_seconds: int) -> bool:
    from datetime import datetime

    try:
        ta = datetime.fromisoformat(a.capture_timestamp)  # type: ignore[arg-type]
        tb = datetime.fromisoformat(b.capture_timestamp)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True  # can't compare → don't let time block the merge
    return abs((ta - tb).total_seconds()) <= window_seconds


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
    weights: tuple[float, float, float, float],
    filter_log: list[dict[str, Any]],
) -> list[_Asset]:
    keep: set[str] = set()
    for bucket, members in clusters.items():
        # S-2.10.2: rank within a location bucket by the full combined score
        # (incl. specialness) so the cap never discards the standout shot.
        sorted_members = sorted(
            members,
            key=lambda a: (-_combined_score(a, weights, 1), a.key),
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
                    **_scores(a),
                }
            )
    return [a for a in assets if a.key in keep]


def _detect_montage_groups(
    assets: list[_Asset],
    *,
    min_members: int,
    window_s: int,
    phash_hamming: int,
    filter_log: list[dict[str, Any]],
) -> list[list[str]]:
    """Find dense same-backdrop photo bursts (S-2.11.4): photos at one ~1km GPS
    cell, within a short window, with near-identical pHash. Returns groups of
    asset.key (ordered by capture time). Photos only; GPS required."""
    cells: dict[tuple[float, float], list[_Asset]] = {}
    for a in assets:
        if a.scene_index is not None or a.gps_lat is None or a.gps_lon is None:
            continue  # photos with GPS only
        cells.setdefault((round(a.gps_lat, _VIEWPOINT_CELL_DP), round(a.gps_lon, _VIEWPOINT_CELL_DP)), []).append(a)
    groups: list[list[str]] = []
    for cell, members in cells.items():
        if len(members) < min_members:
            continue
        for run in _montage_runs(members, window_s, phash_hamming):
            if len(run) >= min_members:
                groups.append([a.key for a in run])
                filter_log.append(
                    {
                        "decision": "montage_group",
                        "reason": "dense_same_backdrop_cluster",
                        "cell": f"{cell[0]},{cell[1]}",
                        "member_count": len(run),
                        "keys": [a.key for a in run],
                    }
                )
    return groups


def _montage_runs(
    members: list[_Asset], window_s: int, phash_hamming: int
) -> list[list[_Asset]]:
    """Split a GPS cell's photos into time+backdrop runs: a new run starts when
    the gap to the run's first member exceeds `window_s` OR the pHash distance to
    the run anchor exceeds `phash_hamming`."""
    ordered = sorted(members, key=lambda a: (a.capture_timestamp or "", a.key))
    runs: list[list[_Asset]] = []
    cur: list[_Asset] = []
    for a in ordered:
        if not cur:
            cur = [a]
            continue
        anchor = cur[0]
        same_backdrop = (
            anchor.phash_hex
            and a.phash_hex
            and _hamming_hex(a.phash_hex, anchor.phash_hex) <= phash_hamming
        )
        if same_backdrop and _within_window(a, anchor, window_s):
            cur.append(a)
        else:
            runs.append(cur)
            cur = [a]
    if cur:
        runs.append(cur)
    return runs


def _cap_gps_viewpoints(
    assets: list[_Asset],
    cap: int,
    weights: tuple[float, float, float, float],
    filter_log: list[dict[str, Any]],
    *,
    exempt_keys: set[str] | None = None,
) -> list[_Asset]:
    """Keep at most `cap` candidates per ~1km GPS cell (T-2.11.1.6), the best by
    combined score. Forces the judge to fill the target from many places rather
    than over-picking one iconic overlook. Assets without GPS (videos) and any
    in `exempt_keys` (montage members, S-2.11.4) are kept regardless."""
    exempt = exempt_keys or set()
    by_cell: dict[tuple[float, float], list[_Asset]] = {}
    keep: set[str] = set()
    for a in assets:
        if a.gps_lat is None or a.gps_lon is None or a.key in exempt:
            keep.add(a.key)  # no-GPS / montage members exempt
            continue
        by_cell.setdefault((round(a.gps_lat, _VIEWPOINT_CELL_DP), round(a.gps_lon, _VIEWPOINT_CELL_DP)), []).append(a)
    for cell, members in by_cell.items():
        ranked = sorted(members, key=lambda a: (-_combined_score(a, weights, 1), a.key))
        for a in ranked[:cap]:
            keep.add(a.key)
        for a in ranked[cap:]:
            filter_log.append(
                {
                    "key": a.key,
                    "decision": "drop",
                    "reason": "viewpoint_candidate_cap",
                    "cell": f"{cell[0]},{cell[1]}",
                    "cap": cap,
                    **_scores(a),
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


def _scores(asset: _Asset) -> dict[str, float]:
    """The three AI signals carried onto every keep/drop log entry so the
    inspect UI can show WHY a borderline item was kept or cut (A-023 F8c)."""
    return {
        "quality_score": asset.quality_score,
        "narrative_relevance": asset.narrative_relevance_score,
        "specialness_score": asset.specialness_score,
    }


def _combined_score(
    asset: _Asset,
    weights: tuple[float, float, float, float],
    cluster_size: int,
) -> float:
    α, β, δ, γ = weights
    diversity = 1.0 / max(cluster_size, 1)
    return (
        α * asset.quality_score
        + β * asset.narrative_relevance_score
        + δ * asset.specialness_score
        + γ * diversity
    )


def _to_candidate_ref(asset: _Asset) -> CandidateRef:
    summary = asset.metadata_summary
    # Lead with an explicit media tag so the judge never has to infer video
    # from the `#scene_index` suffix — it was selecting zero video for a
    # "highlight video" because every candidate read like a still (F2).
    media_tag = "MOTION(video clip)" if asset.scene_index is not None else "STILL(photo)"
    summary = f"{media_tag} | {summary}" if summary else media_tag
    if asset.burst_best_of > 1:
        # Tell the judge this frame stands in for N retakes of one moment.
        tag = f"burst_best_of={asset.burst_best_of}"
        summary = f"{summary} | {tag}" if summary else tag
    return CandidateRef(
        content_hash=asset.content_hash,
        scene_index=asset.scene_index,
        caption=asset.caption or None,
        metadata_summary=summary,
        quality_score=asset.quality_score,
        narrative_relevance=asset.narrative_relevance_score,
        capture_timestamp=asset.capture_timestamp,
        capture_source=asset.capture_source,
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
