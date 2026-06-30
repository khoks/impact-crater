"""Stage 6 — plan compile per ADR-0011 §"Stage 6 — Plan compilation".

Deterministic at M2 — orchestrator second-guess + music-video beat-snap
land in M6 + M4 respectively.

Walks the `ArcJudgment.selected_items`, joins back to the source media
(photo file paths or video scenes), computes final clip durations,
applies aspect-ratio handling (smart-crop for photos / pad-letterbox
for 9:16 video), and persists as `snapshots/{snapshot_id}/plan.json`
per ADR-0006.

Standard mode only at M2; music-video mode raises NotImplementedError
loudly so callers don't silently fall back to standard.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from impact_crater import paths
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.media.music import CutGrid, MusicAnalysis
from impact_crater.pipeline.stage1_ingest import MediaRecord, SceneRecord
from impact_crater.storage.db import connection

log = logging.getLogger(__name__)

# Per-clip display-duration band (S-2.11.1). The MAX is the real fix — a sparse
# selection can no longer balloon a photo to 5-7s; the judge aims for 2-3s. The
# MIN is just a safety floor so an over-packed timeline doesn't flicker (it does
# not force a short 2-photo video over its target).
_PHOTO_MIN_MS = 1000
_PHOTO_MAX_MS = 3000
_VIDEO_MIN_MS = 2000
# At most this many clips from one physical viewpoint (~1km GPS cell). A big
# destination (Grand Canyon rim) spans several cells so it still gets more
# total; a single overlook (Horseshoe Bend) is held to this. (S-2.11.1)
_MAX_CLIPS_PER_LOCATION = 3
_LOCATION_CELL_DP = 2  # round GPS to 2dp ≈ 1.1km
# Burst-montage (S-2.11.4): N member photos at ~0.4-0.6s each, whole montage 2-4s.
_MONTAGE_MEMBER_MIN_MS = 400
_MONTAGE_MEMBER_MAX_MS = 600
_MONTAGE_TARGET_MS = 3000
_MONTAGE_MIN_MS = 2000
_MONTAGE_MAX_MS = 4000
_MONTAGE_MAX_MEMBERS = 8


# ---- Public types ------------------------------------------------------


AspectRatioAction = Literal["smart_crop", "letterbox", "pad", "as_is"]
TransitionType = Literal["cut", "crossfade"]
ClipKind = Literal["photo", "video_scene", "burst_montage"]


class MontageMember(BaseModel):
    """One photo inside a burst-montage clip (S-2.11.4)."""

    model_config = ConfigDict(extra="ignore")
    candidate_ref: str
    source_path: str
    aspect_ratio_action: AspectRatioAction
    duration_ms: int  # per-photo micro-duration (~0.4-0.6s)


class RenderClip(BaseModel):
    """One clip in the final timeline."""

    model_config = ConfigDict(extra="ignore")

    candidate_ref: str
    kind: ClipKind
    source_path: str
    start_seconds: float = 0.0  # video-scene start; ignored for photos
    end_seconds: float = 0.0  # video-scene end; ignored for photos
    intended_duration_ms: int
    aspect_ratio_action: AspectRatioAction
    transition_in: TransitionType = "cut"
    role: str = ""
    notes: str = ""
    # burst_montage only (S-2.11.4): the member photos shown in rapid sequence.
    # Empty for photo/video_scene. Sum of member durations == intended_duration_ms.
    members: list[MontageMember] = Field(default_factory=list)


class StandardMusicSpec(BaseModel):
    """M2 standard-mode music spec.

    Music-video mode (beat-snap, section-mapping) extends this shape
    via `music_analysis` + `cut_grid` per ADR-0012.
    """

    model_config = ConfigDict(extra="ignore")
    audio_path: str
    audio_duration_ms: int
    fade_in_ms: int = 1500
    fade_out_ms: int = 1500
    target_lufs: float = -16.0
    true_peak_db: float = -1.5
    # Populated when mode=music_video (M4); None for standard mode.
    music_analysis: MusicAnalysis | None = None
    cut_grid: CutGrid | None = None
    section_to_media_nl: str | None = None


class RenderPlan(BaseModel):
    """The final compiled plan that Stage 7 executes against."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    project_id: str
    snapshot_id: str
    parent_snapshot_id: str | None = None
    mode: Literal["standard", "music_video"] = "standard"
    target_duration_ms: int
    output_aspect: Literal["16:9"] = "16:9"
    output_width: int = 1920
    output_height: int = 1080
    output_fps: int = 30
    clips: list[RenderClip] = Field(default_factory=list)
    music: StandardMusicSpec | None = None
    arc_reasoning: str = ""
    arc_confidence: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---- Public API --------------------------------------------------------


async def compile_plan(
    *,
    arc_judgment: ArcJudgment,
    ingest_records: list[MediaRecord],
    project_id: str,
    target_duration_seconds: int,
    mode: Literal["standard", "music_video"] = "standard",
    audio: StandardMusicSpec | None = None,
    parent_snapshot_id: str | None = None,
    candidate_refs: list[str] | None = None,
    montage_groups: list[list[str]] | None = None,
) -> RenderPlan:
    """Compile a `RenderPlan` from an `ArcJudgment` + ingest records.

    In `music_video` mode, requires `audio.cut_grid` (computed by the
    runner from `MusicAnalyzer.analyze`); clip durations snap to the
    grid's cut points instead of linear-scaling. Per ADR-0011 + ADR-0012.

    `candidate_refs` (optional): the ordered list of refs Stage 5 saw,
    used for the integer-ref fallback when Opus emits a short integer
    instead of the full content_hash. Smoke-test (Paris run) showed
    this happens occasionally despite the prompt instructions.
    """
    if mode == "music_video":
        if audio is None or audio.cut_grid is None:
            raise ValueError(
                "music_video mode requires StandardMusicSpec.cut_grid "
                "(populated by the runner via MusicAnalyzer.analyze)"
            )

    target_ms = max(target_duration_seconds, 1) * 1000
    clips = _build_clips(
        arc_judgment.selected_items, ingest_records, candidate_refs=candidate_refs
    )
    if not clips:
        raise ValueError("ArcJudgment selected_items produced zero resolvable clips")

    if mode == "music_video":
        assert audio is not None and audio.cut_grid is not None  # narrowed above
        clips = _snap_clips_to_cut_grid(clips, audio.cut_grid, target_ms)
    else:
        # S-2.11.4: collapse dense same-backdrop bursts into one rapid montage
        # FIRST (it represents the whole dense viewpoint), then…
        if montage_groups:
            clips = _collapse_montage_groups(clips, montage_groups)
        # S-2.11.1: …cap clips per physical viewpoint (~1km GPS cell) so one
        # overlook can't dominate, then enforce the snappy per-clip band.
        clips = _cap_per_location(clips, ingest_records, _MAX_CLIPS_PER_LOCATION)
        clips = _scale_to_target(clips, target_ms)
        # Keep each montage's member micro-durations in sync with its (possibly
        # scaled) total so Stage 7's concat length matches the planned length.
        clips = _resync_montage_members(clips)

    snapshot_id = uuid.uuid4().hex[:16]
    plan = RenderPlan(
        project_id=project_id,
        snapshot_id=snapshot_id,
        parent_snapshot_id=parent_snapshot_id,
        mode=mode,
        target_duration_ms=target_ms,
        clips=clips,
        music=audio,
        arc_reasoning=arc_judgment.arc_reasoning,
        arc_confidence=arc_judgment.confidence,
    )
    await _persist(plan)
    return plan


def load_plan(snapshot_id: str, project_id: str) -> RenderPlan:
    """Read back a previously-persisted plan from disk."""
    plan_path = _plan_path(project_id, snapshot_id)
    if not plan_path.is_file():
        raise FileNotFoundError(f"plan.json not found at {plan_path}")
    return RenderPlan.model_validate(json.loads(plan_path.read_text(encoding="utf-8")))


# ---- Clip resolution ---------------------------------------------------


def _build_clips(
    selected: list[SelectedItem],
    ingest_records: list[MediaRecord],
    *,
    candidate_refs: list[str] | None = None,
) -> list[RenderClip]:
    """Resolve each `SelectedItem.candidate_ref` back to a source clip.

    candidate_ref convention:
      - "{content_hash}" for photos
      - "{content_hash}#{scene_index}" for video scenes

    Defensive fallback: if a ref is a short integer (e.g. "2") that
    doesn't match any ingest hash, but `candidate_refs` is supplied
    *and* the integer is a valid index into it, we resolve through that
    list. The Paris smoke test surfaced Opus occasionally emitting
    `[loop.index0]` instead of the ref string; the prompt has been
    tightened, but this guard keeps any future regression from silently
    dropping selected items.
    """
    by_hash: dict[str, MediaRecord] = {r.content_hash: r for r in ingest_records}
    clips: list[RenderClip] = []
    # Sort by placement_position to get a stable timeline.
    for item in sorted(selected, key=lambda s: s.placement_position):
        ref = _coerce_ref(item.candidate_ref, candidate_refs, by_hash)
        if ref != item.candidate_ref:
            log.info(
                "plan: rewrote bad ref %r as %r via candidate_refs index fallback",
                item.candidate_ref,
                ref,
            )
            # The RenderClip needs the resolved ref so downstream consumers
            # don't see "1" — patch the SelectedItem in-place for this loop.
            item = SelectedItem(
                candidate_ref=ref,
                placement_position=item.placement_position,
                intended_duration_ms=item.intended_duration_ms,
                role=item.role,
                notes=item.notes,
            )
        content_hash, scene_index = _split_ref(ref)
        rec = by_hash.get(content_hash)
        if rec is None:
            log.warning("plan: ArcJudgment ref %s missing from ingest set; skipping", item.candidate_ref)
            continue
        if rec.media_type == "photo" and scene_index is None:
            clips.append(_photo_clip(rec, item))
        elif rec.media_type == "video" and scene_index is not None and rec.scenes:
            scene = _find_scene(rec.scenes, scene_index)
            if scene is None:
                log.warning("plan: video %s scene %d missing; skipping", content_hash, scene_index)
                continue
            clips.append(_video_clip(rec, scene, item))
        else:
            log.warning(
                "plan: ref %s media_type=%s scene_index=%s — unsupported combination; skipping",
                item.candidate_ref,
                rec.media_type,
                scene_index,
            )
    return clips


def _collapse_montage_groups(
    clips: list[RenderClip], montage_groups: list[list[str]]
) -> list[RenderClip]:
    """Replace each dense same-backdrop group (S-2.11.4) with ONE burst_montage
    clip at the group's first timeline position; drop the other members."""
    ref_to_group: dict[str, int] = {}
    for gi, g in enumerate(montage_groups):
        for ref in g:
            ref_to_group[ref] = gi
    group_clips: dict[int, list[RenderClip]] = {}
    for c in clips:
        gi = ref_to_group.get(c.candidate_ref)
        if gi is not None:
            group_clips.setdefault(gi, []).append(c)
    anchor_montage: dict[str, RenderClip] = {}
    drop_refs: set[str] = set()
    for members in group_clips.values():
        if len(members) < 2:
            continue  # degenerate — leave as individual clips
        anchor_montage[members[0].candidate_ref] = _montage_clip(members)
        drop_refs.update(m.candidate_ref for m in members[1:])
    if not anchor_montage:
        return clips
    out: list[RenderClip] = []
    for c in clips:
        if c.candidate_ref in anchor_montage:
            out.append(anchor_montage[c.candidate_ref])
        elif c.candidate_ref not in drop_refs:
            out.append(c)
    return out


def _montage_clip(members: list[RenderClip]) -> RenderClip:
    members = members[:_MONTAGE_MAX_MEMBERS]
    n = len(members)
    per = min(max(round(_MONTAGE_TARGET_MS / n), _MONTAGE_MEMBER_MIN_MS), _MONTAGE_MEMBER_MAX_MS)
    return RenderClip(
        candidate_ref=members[0].candidate_ref,
        kind="burst_montage",
        source_path=members[0].source_path,
        intended_duration_ms=per * n,
        aspect_ratio_action=members[0].aspect_ratio_action,
        transition_in="cut",
        role=members[0].role or "montage",
        notes=f"burst-montage of {n} photos at one spot",
        members=[
            MontageMember(
                candidate_ref=m.candidate_ref,
                source_path=m.source_path,
                aspect_ratio_action=m.aspect_ratio_action,
                duration_ms=per,
            )
            for m in members
        ],
    )


def _resync_montage_members(clips: list[RenderClip]) -> list[RenderClip]:
    """After scaling, redistribute a montage clip's total across its members so
    sum(member.duration_ms) == clip.intended_duration_ms exactly (audio sync)."""
    out: list[RenderClip] = []
    for c in clips:
        if c.kind != "burst_montage" or not c.members:
            out.append(c)
            continue
        n = len(c.members)
        base, rem = divmod(c.intended_duration_ms, n)
        out.append(
            c.model_copy(
                update={
                    "members": [
                        m.model_copy(update={"duration_ms": base + (1 if i < rem else 0)})
                        for i, m in enumerate(c.members)
                    ]
                }
            )
        )
    return out


def _cap_per_location(
    clips: list[RenderClip], ingest_records: list[MediaRecord], max_per_loc: int
) -> list[RenderClip]:
    """Drop clips beyond `max_per_loc` from the same ~1km GPS cell, preserving
    the judge's order (keep the first N at each spot). Videos / no-GPS media are
    exempt — they're few and not 'one overlook'. (S-2.11.1, feedback #2.)"""
    by_hash = {r.content_hash: r for r in ingest_records}
    seen: dict[tuple[float, float], int] = {}
    out: list[RenderClip] = []
    for c in clips:
        if c.kind == "burst_montage":
            out.append(c)  # the montage IS the dense viewpoint's representation
            continue
        rec = by_hash.get(c.candidate_ref.split("#", 1)[0])
        cell = (
            (round(rec.gps_lat, _LOCATION_CELL_DP), round(rec.gps_lon, _LOCATION_CELL_DP))
            if rec is not None and rec.gps_lat is not None and rec.gps_lon is not None
            else None
        )
        if cell is not None:
            if seen.get(cell, 0) >= max_per_loc:
                log.info("stage6_capped_viewpoint cell=%s ref=%s", cell, c.candidate_ref)
                continue
            seen[cell] = seen.get(cell, 0) + 1
        out.append(c)
    return out


def _coerce_ref(
    ref: str,
    candidate_refs: list[str] | None,
    by_hash: dict[str, MediaRecord],
) -> str:
    """If `ref` is a short integer (≤4 chars, all digits) that doesn't
    match any ingested content_hash, treat it as an index into
    `candidate_refs` and return the actual ref. Otherwise pass through.
    """
    # Strip any "#scene_index" so the integer test sees just the head.
    head, _, _ = ref.partition("#")
    if head in by_hash:
        return ref  # already a valid hash
    if not candidate_refs:
        return ref
    if not (head.isdigit() and 0 < len(head) <= 4):
        return ref
    try:
        idx = int(head)
    except ValueError:
        return ref
    if 0 <= idx < len(candidate_refs):
        return candidate_refs[idx]
    return ref


def _split_ref(ref: str) -> tuple[str, int | None]:
    if "#" not in ref:
        return (ref, None)
    h, idx = ref.split("#", 1)
    try:
        return (h, int(idx))
    except ValueError:
        return (h, None)


def _find_scene(scenes: list[SceneRecord], idx: int) -> SceneRecord | None:
    return next((s for s in scenes if s.index == idx), None)


def _photo_clip(rec: MediaRecord, item: SelectedItem) -> RenderClip:
    width = int(rec.quick_stats.get("width") or 0)
    height = int(rec.quick_stats.get("height") or 0)
    return RenderClip(
        candidate_ref=item.candidate_ref,
        kind="photo",
        source_path=rec.source_path,
        intended_duration_ms=max(item.intended_duration_ms, 250),
        aspect_ratio_action=_pick_action_for_photo(width, height),
        transition_in="cut",
        role=item.role,
        notes=item.notes or "",
    )


def _video_clip(rec: MediaRecord, scene: SceneRecord, item: SelectedItem) -> RenderClip:
    width = int(rec.quick_stats.get("width") or 0)
    height = int(rec.quick_stats.get("height") or 0)
    # Use the scene's actual bounds; final duration may be scaled later.
    natural_duration_ms = max(int((scene.end_seconds - scene.start_seconds) * 1000), 500)
    return RenderClip(
        candidate_ref=item.candidate_ref,
        kind="video_scene",
        source_path=rec.source_path,
        start_seconds=scene.start_seconds,
        end_seconds=scene.end_seconds,
        intended_duration_ms=min(item.intended_duration_ms or natural_duration_ms, natural_duration_ms),
        aspect_ratio_action=_pick_action_for_video(width, height),
        transition_in="cut",
        role=item.role,
        notes=item.notes or "",
    )


def _pick_action_for_photo(width: int, height: int) -> AspectRatioAction:
    """Photos: 16:9-ish → as_is; portrait or square → smart_crop."""
    if width <= 0 or height <= 0:
        return "smart_crop"
    ratio = width / height
    target = 16.0 / 9.0
    # Within ±10% of 16:9 → use as-is and let ffmpeg's scale-and-pad handle minor mismatch.
    if abs(ratio - target) / target <= 0.10:
        return "as_is"
    return "smart_crop"


def _pick_action_for_video(width: int, height: int) -> AspectRatioAction:
    """Videos: 16:9-ish → as_is; portrait → letterbox (pad with black)."""
    if width <= 0 or height <= 0:
        return "letterbox"
    ratio = width / height
    target = 16.0 / 9.0
    if abs(ratio - target) / target <= 0.10:
        return "as_is"
    if ratio < target:
        return "letterbox"
    return "pad"


# ---- Duration scaling --------------------------------------------------


def _snap_clips_to_cut_grid(
    clips: list[RenderClip],
    cut_grid: CutGrid,
    target_ms: int,
) -> list[RenderClip]:
    """Snap clip boundaries onto the beat grid (music-video mode).

    Stage 5 already paced the clips for the target duration; the grid's
    job is to land each *transition* on a beat, not to dictate one clip
    per beat interval. Linear-scale the clip durations so the timeline
    covers the target, then snap each cumulative clip boundary to the
    nearest cut point. Every cut lands on a beat and the video still
    runs ~target_ms.

    (The pre-2026-06-11 behavior assigned one clip per grid interval and
    dropped the rest of the timeline: a 13-clip 60s plan rendered 25.3s
    of video and the song stopped mid-crescendo.)
    """
    cuts = sorted({c for c in cut_grid.cut_points_ms if 0 <= c <= target_ms})
    if len(cuts) < 2:
        # Degenerate grid — fall back to linear scale.
        return _linear_scale(clips, target_ms)

    scaled = _linear_scale(clips, target_ms)

    out: list[RenderClip] = []
    prev_ms = 0
    intended_elapsed = 0
    for i, clip in enumerate(scaled):
        intended_elapsed += clip.intended_duration_ms
        if i == len(scaled) - 1:
            boundary = max(target_ms, prev_ms + 250)
        else:
            boundary = _nearest_cut(cuts, intended_elapsed, floor=prev_ms + 250)
        snapped_ms = boundary - prev_ms
        if clip.kind == "video_scene":
            scene_max = max(int((clip.end_seconds - clip.start_seconds) * 1000), 250)
            snapped_ms = min(snapped_ms, scene_max)
        out.append(clip.model_copy(update={"intended_duration_ms": snapped_ms}))
        prev_ms += snapped_ms
    return out


def _nearest_cut(cuts: list[int], t: int, *, floor: int) -> int:
    """The cut point nearest `t` that's at least `floor`; `floor` keeps
    boundaries monotonic with a 250ms minimum clip duration."""
    candidates = [c for c in cuts if c >= floor]
    if not candidates:
        return max(t, floor)
    return min(candidates, key=lambda c: abs(c - t))


def _linear_scale(
    clips: list[RenderClip], target_ms: int, *, tolerance: float = 0.10
) -> list[RenderClip]:
    """Legacy proportional scale (photos stretch, video capped at natural).

    Used ONLY by music-video beat-snapping, where the cut grid — not a per-clip
    duration band — drives pacing (beats can be far shorter than 1.5s). Standard
    mode uses _scale_to_target with the S-2.11.1 caps instead.
    """
    total = sum(c.intended_duration_ms for c in clips)
    if total <= 0:
        return clips
    if abs((total - target_ms) / target_ms) <= tolerance:
        return clips
    factor = target_ms / total
    out: list[RenderClip] = []
    for c in clips:
        new_ms = max(int(c.intended_duration_ms * factor), 250)
        if c.kind == "video_scene":
            scene_max = max(int((c.end_seconds - c.start_seconds) * 1000), 250)
            new_ms = min(new_ms, scene_max)
        out.append(c.model_copy(update={"intended_duration_ms": new_ms}))
    deficit = target_ms - sum(c.intended_duration_ms for c in out)
    if deficit > 0:
        photo_idxs = [i for i, c in enumerate(out) if c.kind == "photo"]
        if photo_idxs:
            extra = (deficit + len(photo_idxs) - 1) // len(photo_idxs)
            for idx in photo_idxs:
                out[idx] = out[idx].model_copy(
                    update={"intended_duration_ms": out[idx].intended_duration_ms + extra}
                )
    return out


def _clip_band(c: RenderClip) -> tuple[int, int]:
    """(min, max) display duration for a clip (S-2.11.1).

    Photos read in ~2-3s; a 5s hold feels frozen. Videos play >=2s at their
    natural pace (a <2s flash is jerky noise); a video's max is its natural
    length so it never freezes on a held last frame.
    """
    if c.kind == "burst_montage":
        return (_MONTAGE_MIN_MS, _MONTAGE_MAX_MS)
    if c.kind == "video_scene":
        natural = max(int((c.end_seconds - c.start_seconds) * 1000), 0)
        hi = max(natural, _VIDEO_MIN_MS)
        return (min(_VIDEO_MIN_MS, hi), hi)
    return (_PHOTO_MIN_MS, _PHOTO_MAX_MS)


def _scale_to_target(
    clips: list[RenderClip], target_ms: int, *, tolerance: float = 0.10
) -> list[RenderClip]:
    """Fit the timeline to the target while keeping every clip inside its
    per-kind duration band (S-2.11.1): photos 1.5-3s, videos 2s-to-natural.

    Photos no longer stretch to fill a target the judge under-populated — they
    are hard-capped, so too few clips yield a SHORTER video, not 5-7s photos.
    The judge is instructed to pick enough 2-3s clips to fill the target.
    """
    # 1. Clamp every clip into its band first (hard caps, regardless of judge).
    capped: list[RenderClip] = []
    for c in clips:
        lo, hi = _clip_band(c)
        capped.append(
            c.model_copy(update={"intended_duration_ms": min(max(c.intended_duration_ms, lo), hi)})
        )

    total = sum(c.intended_duration_ms for c in capped)
    if total <= 0:
        return capped
    if abs((total - target_ms) / target_ms) <= tolerance:
        return capped

    if total > target_ms:
        # Too long: shrink proportionally toward target, never below each
        # clip's band floor (slightly over target is fine if all hit floor).
        factor = target_ms / total
        out: list[RenderClip] = []
        for c in capped:
            lo, _ = _clip_band(c)
            out.append(
                c.model_copy(update={"intended_duration_ms": max(int(c.intended_duration_ms * factor), lo)})
            )
        return out

    # Under target even at the per-clip caps: accept a shorter video rather than
    # stretching photos. Surface it so a too-thin selection is visible.
    log.info(
        "stage6_under_target capped_total_ms=%d target_ms=%d clips=%d "
        "(judge selected too few clips to fill the target at 2-3s each)",
        total,
        target_ms,
        len(capped),
    )
    return capped


# ---- Persistence -------------------------------------------------------


async def _persist(plan: RenderPlan) -> None:
    """Write `plan.json`, create the snapshot directory, insert DB row."""
    plan_path = _plan_path(plan.project_id, plan.snapshot_id)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    async with connection() as db:
        # Auto-create the project row when the runner is the first writer.
        await db.execute(
            "INSERT OR IGNORE INTO projects (id, name) VALUES (?, ?)",
            (plan.project_id, plan.project_id),
        )
        await db.execute(
            """
            INSERT INTO snapshots
                (id, project_id, parent_snapshot_id, plan_path, render_path, render_status)
            VALUES (?, ?, ?, ?, NULL, 'pending')
            """,
            (plan.snapshot_id, plan.project_id, plan.parent_snapshot_id, str(plan_path)),
        )
        await db.commit()


def _plan_path(project_id: str, snapshot_id: str) -> Path:
    return (
        paths.projects_dir() / project_id / "snapshots" / snapshot_id / "plan.json"
    )


def snapshot_dir(project_id: str, snapshot_id: str) -> Path:
    p = paths.projects_dir() / project_id / "snapshots" / snapshot_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def apply_overrides(plan: RenderPlan, overrides: list) -> RenderPlan:
    """Apply Override objects to a RenderPlan. Returns a new plan instance.

    Implementation per ADR-0011 § Override types. M6 baseline supports
    `drop_item` and `reorder`; `shorten`/`lengthen`/`swap` log + skip.
    """
    if not overrides:
        return plan
    new_clips = list(plan.clips)
    # Sort overrides so drops are applied last (positions don't shift).
    drops: list[int] = []
    reorders: list[tuple[int, int]] = []  # (from, to)
    for ov in overrides:
        # Accept both Pydantic Override + plain-dict shapes.
        if hasattr(ov, "type"):
            ov_type = ov.type
            pos = ov.target_position
            change = getattr(ov, "proposed_change", None)
        else:
            ov_type = ov.get("type")
            pos = ov.get("target_position")
            change = ov.get("proposed_change", {})
        if pos is None:
            continue
        if ov_type == "drop_item":
            drops.append(pos)
        elif ov_type == "reorder":
            new_pos = change.get("new_position") if isinstance(change, dict) else None
            if isinstance(new_pos, int):
                reorders.append((pos, new_pos))
    # Apply reorders first.
    for src, dst in reorders:
        if 0 <= src < len(new_clips) and 0 <= dst < len(new_clips):
            clip = new_clips.pop(src)
            new_clips.insert(dst, clip)
    # Then drops (descending so indices stay valid).
    for pos in sorted(drops, reverse=True):
        if 0 <= pos < len(new_clips):
            new_clips.pop(pos)
    return plan.model_copy(update={"clips": new_clips})
