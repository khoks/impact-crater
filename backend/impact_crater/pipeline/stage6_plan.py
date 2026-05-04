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
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from impact_crater import paths
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.pipeline.stage1_ingest import MediaRecord, SceneRecord
from impact_crater.storage.db import connection

log = logging.getLogger(__name__)


# ---- Public types ------------------------------------------------------


AspectRatioAction = Literal["smart_crop", "letterbox", "pad", "as_is"]
TransitionType = Literal["cut", "crossfade"]
ClipKind = Literal["photo", "video_scene"]


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


class StandardMusicSpec(BaseModel):
    """M2 standard-mode music spec.

    Music-video mode (beat-snap, section-mapping) lands at M4; this is
    the simpler "background music under the video" shape per ADR-0012
    standard mode.
    """

    model_config = ConfigDict(extra="ignore")
    audio_path: str
    audio_duration_ms: int
    fade_in_ms: int = 1500
    fade_out_ms: int = 1500
    target_lufs: float = -16.0
    true_peak_db: float = -1.5


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
) -> RenderPlan:
    """Compile a `RenderPlan` from an `ArcJudgment` + ingest records."""
    if mode == "music_video":
        raise NotImplementedError(
            "music_video mode lands at M4 (E-2.5); M2 supports standard mode only"
        )

    target_ms = max(target_duration_seconds, 1) * 1000
    clips = _build_clips(arc_judgment.selected_items, ingest_records)
    if not clips:
        raise ValueError("ArcJudgment selected_items produced zero resolvable clips")
    clips = _scale_to_target(clips, target_ms)

    snapshot_id = uuid.uuid4().hex[:16]
    plan = RenderPlan(
        project_id=project_id,
        snapshot_id=snapshot_id,
        parent_snapshot_id=parent_snapshot_id,
        mode="standard",
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
) -> list[RenderClip]:
    """Resolve each `SelectedItem.candidate_ref` back to a source clip.

    candidate_ref convention:
      - "{content_hash}" for photos
      - "{content_hash}#{scene_index}" for video scenes
    """
    by_hash: dict[str, MediaRecord] = {r.content_hash: r for r in ingest_records}
    clips: list[RenderClip] = []
    # Sort by placement_position to get a stable timeline.
    for item in sorted(selected, key=lambda s: s.placement_position):
        content_hash, scene_index = _split_ref(item.candidate_ref)
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


def _scale_to_target(
    clips: list[RenderClip], target_ms: int, *, tolerance: float = 0.10
) -> list[RenderClip]:
    """Scale each clip's duration linearly so the sum is within ±tolerance of target.

    Photos can stretch to any duration; video scenes are capped by their natural length.
    """
    total = sum(c.intended_duration_ms for c in clips)
    if total <= 0:
        return clips

    diff_ratio = (total - target_ms) / target_ms
    if abs(diff_ratio) <= tolerance:
        return clips

    factor = target_ms / total
    out: list[RenderClip] = []
    for c in clips:
        new_ms = max(int(c.intended_duration_ms * factor), 250)
        if c.kind == "video_scene":
            scene_max = max(int((c.end_seconds - c.start_seconds) * 1000), 250)
            new_ms = min(new_ms, scene_max)
        out.append(c.model_copy(update={"intended_duration_ms": new_ms}))

    # If video-scene caps left us short, distribute the remainder across photos.
    new_total = sum(c.intended_duration_ms for c in out)
    deficit = target_ms - new_total
    if deficit > 0:
        photo_idxs = [i for i, c in enumerate(out) if c.kind == "photo"]
        if photo_idxs:
            extra = math.ceil(deficit / len(photo_idxs))
            for idx in photo_idxs:
                out[idx] = out[idx].model_copy(
                    update={"intended_duration_ms": out[idx].intended_duration_ms + extra}
                )
    return out


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
