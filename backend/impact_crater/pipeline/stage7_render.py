"""Stage 7 — ffmpeg render per ADR-0010 + ADR-0011 + ADR-0012 (standard mode).

Reads a `RenderPlan` (from Stage 6 / S-2.3.2) and writes
`snapshots/{snapshot_id}/render.mp4`.

Pipeline:
  1. Pre-render each clip to a normalized 1920×1080 / 30 fps H.264 / yuv420p
     segment with no audio. Photos → `-loop 1 -t <dur>`; video scenes →
     `-ss <start> -t <dur>`. Aspect-ratio actions (`as_is`, `smart_crop`,
     `letterbox`, `pad`) become specific scale/crop/pad filter chains.
  2. Concatenate segments via the concat demuxer.
  3. Two-pass loudnorm on the user's audio (target -16 LUFS / TP -1.5 dB),
     atrim to target_duration, afade-in 1.5s / afade-out 1.5s.
  4. Final mux: video + normalized audio → render.mp4 with faststart.

The worker pool's `register_subprocess` is used so `cancel()` can SIGTERM
in-flight ffmpeg children with a grace period.

This is the M2 baseline — single ffmpeg per clip, sequential. M3+ may
optimize with a single complex-filter graph; correctness matters more
than speed at MVP scale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from impact_crater import telemetry
from impact_crater.media import ffmpeg as ff
from impact_crater.pipeline.stage6_plan import RenderClip, RenderPlan, snapshot_dir
from impact_crater.storage.db import connection
from impact_crater.workers import WorkerPool

log = logging.getLogger(__name__)


# ---- Public types ------------------------------------------------------


@dataclass
class RenderResult:
    snapshot_id: str
    render_path: str
    duration_ms: int
    output_bytes: int
    ffmpeg_exit_code: int
    status: str  # "success" | "failure" | "cancelled"


class RenderError(RuntimeError):
    """Surfaced when an ffmpeg subprocess fails or the plan is invalid."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        ffmpeg_exit_code: int | None = None,
        stderr_excerpt: str = "",
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.ffmpeg_exit_code = ffmpeg_exit_code
        self.stderr_excerpt = stderr_excerpt


# ---- Constants ---------------------------------------------------------


_OUT_W = 1920
_OUT_H = 1080
_OUT_FPS = 30
_X264_PRESET = "veryfast"  # M2 baseline; M3+ may bump for quality
_X264_CRF = 20
_AUDIO_CODEC = "aac"
_AUDIO_BITRATE = "192k"


# ---- Public API --------------------------------------------------------


async def render_plan(
    plan: RenderPlan,
    *,
    correlation_id: str,
    pool: WorkerPool | None = None,
) -> RenderResult:
    """Execute `plan` end-to-end and return the rendered MP4 path + stats.

    `correlation_id` is forwarded to the RenderEvent telemetry record so
    the cost-summary aggregation can stitch it back to the parent job.
    """
    started_at = time.time()
    snap_dir = snapshot_dir(plan.project_id, plan.snapshot_id)
    work_dir = snap_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    render_path = snap_dir / "render.mp4"

    try:
        await _set_render_status(plan.snapshot_id, "in_progress", None)

        # Phase 1 — pre-render each clip into a normalized segment.
        segment_paths = await _prerender_clips(plan, work_dir, pool=pool)

        # Phase 2 — concatenate via concat demuxer.
        concat_video = work_dir / "concat.mp4"
        await _concat_segments(segment_paths, concat_video, pool=pool)

        # Phase 3 — audio normalize + fade + trim, if music supplied.
        if plan.music is not None:
            audio_path = work_dir / "audio.m4a"
            # Trim + fade against the ACTUAL timeline, not the requested
            # target: clip durations land within ±10% of target (or are
            # capped by video-scene length), and the mux below uses
            # -shortest. Trimming to target_duration_ms put the fade-out
            # past the end of the video — the song just stopped cold.
            timeline_ms = sum(c.intended_duration_ms for c in plan.clips)
            await _normalize_audio(
                Path(plan.music.audio_path),
                audio_path,
                target_lufs=plan.music.target_lufs,
                true_peak_db=plan.music.true_peak_db,
                target_duration_ms=timeline_ms,
                fade_in_ms=plan.music.fade_in_ms,
                fade_out_ms=plan.music.fade_out_ms,
                pool=pool,
            )
            await _mux_video_audio(concat_video, audio_path, render_path, pool=pool)
        else:
            # No music: copy concat into place.
            shutil.copy2(concat_video, render_path)

        duration_ms = int((time.time() - started_at) * 1000)
        output_bytes = render_path.stat().st_size if render_path.is_file() else 0

        telemetry.emit(
            telemetry.RenderEvent(
                project_id=plan.project_id,
                snapshot_id=plan.snapshot_id,
                duration_ms=duration_ms,
                output_bytes=output_bytes,
                render_status="success",
                ffmpeg_exit_code=0,
                correlation_id=correlation_id,
            )
        )
        await _set_render_status(plan.snapshot_id, "success", str(render_path))

        return RenderResult(
            snapshot_id=plan.snapshot_id,
            render_path=str(render_path),
            duration_ms=duration_ms,
            output_bytes=output_bytes,
            ffmpeg_exit_code=0,
            status="success",
        )
    except RenderError as exc:
        duration_ms = int((time.time() - started_at) * 1000)
        telemetry.emit(
            telemetry.RenderEvent(
                project_id=plan.project_id,
                snapshot_id=plan.snapshot_id,
                duration_ms=duration_ms,
                output_bytes=0,
                render_status="failure",
                ffmpeg_exit_code=exc.ffmpeg_exit_code,
                error_excerpt=exc.stderr_excerpt[:2048],
                correlation_id=correlation_id,
            )
        )
        await _set_render_status(plan.snapshot_id, "failure", None)
        raise


# ---- Phase 1: per-clip pre-render -------------------------------------


async def _prerender_clips(
    plan: RenderPlan, work_dir: Path, *, pool: WorkerPool | None
) -> list[Path]:
    """Render each clip to a normalized H.264 segment.

    Sequential at M2 — running concurrent ffmpegs against the same disk
    contends for I/O without a real win at MVP clip counts (≤50). The
    worker pool's ffmpeg class would let us parallelize 2-3 at a time;
    leave that for M3+ once we have render-time profiling data.
    """
    out_paths: list[Path] = []
    log.info(
        "stage7_prerender_start snapshot_id=%s clip_count=%d",
        plan.snapshot_id,
        len(plan.clips),
    )
    for i, clip in enumerate(plan.clips):
        seg_path = work_dir / f"seg-{i:04d}.mp4"
        log.debug(
            "stage7_clip_render snapshot_id=%s clip=%d/%d candidate_ref=%s "
            "kind=%s duration_ms=%d",
            plan.snapshot_id,
            i + 1,
            len(plan.clips),
            clip.candidate_ref,
            clip.kind,
            clip.intended_duration_ms,
        )
        await _prerender_one(clip, seg_path, pool=pool)
        out_paths.append(seg_path)
    log.info(
        "stage7_prerender_done snapshot_id=%s clip_count=%d",
        plan.snapshot_id,
        len(plan.clips),
    )
    return out_paths


async def _prerender_one(
    clip: RenderClip,
    out_path: Path,
    *,
    pool: WorkerPool | None,
) -> None:
    if clip.kind == "burst_montage":  # S-2.11.4
        await _prerender_montage(clip, out_path, pool=pool)
        return

    duration_s = max(clip.intended_duration_ms / 1000.0, 0.25)
    vf = _video_filter(clip.aspect_ratio_action)

    if clip.kind == "photo":
        args = [
            "-y",
            "-loop", "1",
            "-t", f"{duration_s:.3f}",
            "-i", clip.source_path,
            "-vf", vf,
            "-r", str(_OUT_FPS),
            "-c:v", "libx264",
            "-preset", _X264_PRESET,
            "-crf", str(_X264_CRF),
            "-pix_fmt", "yuv420p",
            # Force TV-range (limited) — JPEG sources default to PC range
            # (full), which ffprobe reports as yuvj420p. Limited-range is
            # the broader-compatible choice for YouTube + most players.
            "-color_range", "tv",
            "-an",
            str(out_path),
        ]
    else:  # video_scene
        args = [
            "-y",
            "-ss", f"{clip.start_seconds:.3f}",
            "-t", f"{duration_s:.3f}",
            "-i", clip.source_path,
            "-vf", vf,
            "-r", str(_OUT_FPS),
            "-c:v", "libx264",
            "-preset", _X264_PRESET,
            "-crf", str(_X264_CRF),
            "-pix_fmt", "yuv420p",
            # Force TV-range (limited) — JPEG sources default to PC range
            # (full), which ffprobe reports as yuvj420p. Limited-range is
            # the broader-compatible choice for YouTube + most players.
            "-color_range", "tv",
            "-an",
            str(out_path),
        ]

    rc, _stdout, stderr = await _run(args, pool=pool)
    if rc != 0:
        stderr_str = stderr.decode("utf-8", errors="replace")
        log.error(
            "stage7_clip_failed candidate_ref=%s kind=%s ffmpeg_exit_code=%d "
            "stderr_tail=%r",
            clip.candidate_ref,
            clip.kind,
            rc,
            stderr_str[-300:],
        )
        raise RenderError(
            f"clip pre-render failed for {clip.candidate_ref!r}",
            stage="prerender",
            ffmpeg_exit_code=rc,
            stderr_excerpt=stderr_str,
        )


async def _prerender_montage(
    clip: RenderClip, out_path: Path, *, pool: WorkerPool | None
) -> None:
    """Render each montage member photo to a tiny normalized segment, then
    concat them (stream-copy) into one montage segment that is byte-compatible
    with the other top-level segments (S-2.11.4)."""
    work = out_path.parent
    stem = out_path.stem
    member_segs: list[Path] = []
    for j, m in enumerate(clip.members):
        seg = work / f"{stem}-m{j:03d}.mp4"
        dur_s = max(m.duration_ms / 1000.0, 0.2)
        args = [
            "-y", "-loop", "1", "-t", f"{dur_s:.3f}", "-i", m.source_path,
            "-vf", _video_filter(m.aspect_ratio_action), "-r", str(_OUT_FPS),
            "-c:v", "libx264", "-preset", _X264_PRESET, "-crf", str(_X264_CRF),
            "-pix_fmt", "yuv420p", "-color_range", "tv", "-an", str(seg),
        ]
        rc, _stdout, stderr = await _run(args, pool=pool)
        if rc != 0:
            raise RenderError(
                f"montage member pre-render failed for {m.candidate_ref!r}",
                stage="prerender",
                ffmpeg_exit_code=rc,
                stderr_excerpt=stderr.decode("utf-8", errors="replace"),
            )
        member_segs.append(seg)
    list_file = out_path.with_suffix(".members.txt")
    list_file.write_text(
        "\n".join(f"file '{s.as_posix()}'" for s in member_segs) + "\n", encoding="utf-8"
    )
    args = ["-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)]
    rc, _stdout, stderr = await _run(args, pool=pool)
    if rc != 0:
        raise RenderError(
            "montage member concat failed",
            stage="concat",
            ffmpeg_exit_code=rc,
            stderr_excerpt=stderr.decode("utf-8", errors="replace"),
        )


def _video_filter(action: str) -> str:
    """Build the -vf chain for the requested aspect-ratio action.

    All actions land at exactly _OUT_W × _OUT_H (1920×1080) yuv420p; the
    differences are how source pixels map onto that canvas.
    """
    target = f"{_OUT_W}:{_OUT_H}"
    if action == "letterbox":
        return (
            f"scale=w={_OUT_W}:h={_OUT_H}:force_original_aspect_ratio=decrease,"
            f"pad={_OUT_W}:{_OUT_H}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={_OUT_FPS},format=yuv420p"
        )
    if action == "pad":
        # Wider-than-16:9 source → fit to height, pad sides.
        return (
            f"scale=w={_OUT_W}:h={_OUT_H}:force_original_aspect_ratio=decrease,"
            f"pad={_OUT_W}:{_OUT_H}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={_OUT_FPS},format=yuv420p"
        )
    if action == "smart_crop":
        # M2 baseline = center-crop after a scale-to-cover. saliency-aware
        # smart_crop via smartcrop.py can plug in here in M3+ by pre-computing
        # the crop bbox at plan-compile time and emitting an explicit crop=
        # filter; for now center-crop is the deterministic fallback.
        return (
            f"scale=w={_OUT_W}:h={_OUT_H}:force_original_aspect_ratio=increase,"
            f"crop={_OUT_W}:{_OUT_H},setsar=1,fps={_OUT_FPS}"
        )
    # `as_is` — scale to fit + minor pad to absorb any rounding.
    return (
        f"scale=w={_OUT_W}:h={_OUT_H}:force_original_aspect_ratio=decrease,"
        f"pad={_OUT_W}:{_OUT_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1,fps={_OUT_FPS},format=yuv420p"
    )


# ---- Phase 2: concat ---------------------------------------------------


async def _concat_segments(
    segments: list[Path], out_path: Path, *, pool: WorkerPool | None
) -> None:
    if not segments:
        raise RenderError("no segments to concatenate", stage="concat")

    list_file = out_path.with_name("concat-list.txt")
    list_file.write_text(
        "\n".join(f"file '{seg.as_posix()}'" for seg in segments) + "\n",
        encoding="utf-8",
    )
    args = [
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_path),
    ]
    rc, _stdout, stderr = await _run(args, pool=pool)
    if rc != 0:
        raise RenderError(
            "segment concat failed",
            stage="concat",
            ffmpeg_exit_code=rc,
            stderr_excerpt=stderr.decode("utf-8", errors="replace"),
        )


# ---- Phase 3: audio normalize + fade + trim ---------------------------


async def _normalize_audio(
    src: Path,
    out_path: Path,
    *,
    target_lufs: float,
    true_peak_db: float,
    target_duration_ms: int,
    fade_in_ms: int,
    fade_out_ms: int,
    pool: WorkerPool | None,
) -> None:
    """Two-pass loudnorm + afade + atrim → AAC m4a."""
    # Pass 1 — measure.
    measure_args = [
        "-y",
        "-i", str(src),
        "-af",
        f"loudnorm=I={target_lufs}:TP={true_peak_db}:LRA=11:print_format=json",
        "-f", "null",
        "-",
    ]
    rc, _stdout, stderr = await _run(measure_args, pool=pool)
    if rc != 0:
        raise RenderError(
            "loudnorm pass-1 measurement failed",
            stage="loudnorm",
            ffmpeg_exit_code=rc,
            stderr_excerpt=stderr.decode("utf-8", errors="replace"),
        )

    measured = _parse_loudnorm_json(stderr.decode("utf-8", errors="replace"))

    # Pass 2 — apply with measured values + fades + trim.
    target_s = target_duration_ms / 1000.0
    fade_in_s = fade_in_ms / 1000.0
    fade_out_s = fade_out_ms / 1000.0
    fade_out_start = max(target_s - fade_out_s, 0.0)

    af_chain = (
        f"loudnorm=I={target_lufs}:TP={true_peak_db}:LRA=11"
        f":measured_I={measured['input_i']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true:print_format=summary,"
        f"afade=t=in:st=0:d={fade_in_s},"
        f"afade=t=out:st={fade_out_start}:d={fade_out_s},"
        f"atrim=0:{target_s}"
    )
    apply_args = [
        "-y",
        "-i", str(src),
        "-af", af_chain,
        "-c:a", _AUDIO_CODEC,
        "-b:a", _AUDIO_BITRATE,
        "-ar", "48000",
        "-ac", "2",
        str(out_path),
    ]
    rc, _stdout, stderr = await _run(apply_args, pool=pool)
    if rc != 0:
        raise RenderError(
            "loudnorm pass-2 apply failed",
            stage="loudnorm",
            ffmpeg_exit_code=rc,
            stderr_excerpt=stderr.decode("utf-8", errors="replace"),
        )


def _parse_loudnorm_json(stderr_text: str) -> dict[str, str]:
    """Pull the JSON object ffmpeg's loudnorm prints to stderr in pass 1."""
    # ffmpeg writes the JSON among other diagnostics; grab the `{...}` block.
    match = re.search(r"\{[\s\S]*?\}", stderr_text)
    if not match:
        raise RenderError(
            "could not parse loudnorm JSON from pass-1 stderr",
            stage="loudnorm",
            stderr_excerpt=stderr_text[-2048:],
        )
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise RenderError(
            f"loudnorm JSON parse error: {e}",
            stage="loudnorm",
            stderr_excerpt=match.group(0)[:512],
        ) from e

    out: dict[str, str] = {}
    for key in ("input_i", "input_lra", "input_tp", "input_thresh", "target_offset"):
        if key not in obj:
            raise RenderError(
                f"loudnorm JSON missing key {key!r}",
                stage="loudnorm",
                stderr_excerpt=str(obj)[:512],
            )
        out[key] = str(obj[key])
    return out


# ---- Phase 4: mux ------------------------------------------------------


async def _mux_video_audio(
    video: Path, audio: Path, out_path: Path, *, pool: WorkerPool | None
) -> None:
    args = [
        "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "copy",
        "-shortest",
        "-movflags", "+faststart",
        str(out_path),
    ]
    rc, _stdout, stderr = await _run(args, pool=pool)
    if rc != 0:
        raise RenderError(
            "final mux failed",
            stage="mux",
            ffmpeg_exit_code=rc,
            stderr_excerpt=stderr.decode("utf-8", errors="replace"),
        )


# ---- Subprocess runner -------------------------------------------------


async def _run(
    args: list[str],
    *,
    pool: WorkerPool | None,
) -> tuple[int, bytes, bytes]:
    """Run ffmpeg with `args`; register with the pool if supplied."""
    on_started = pool.register_subprocess if pool else None
    return await ff.run_ffmpeg_async(args, on_subprocess_started=on_started)


async def _set_render_status(
    snapshot_id: str, status: str, render_path: str | None
) -> None:
    async with connection() as db:
        if render_path is None:
            await db.execute(
                "UPDATE snapshots SET render_status = ? WHERE id = ?",
                (status, snapshot_id),
            )
        else:
            await db.execute(
                "UPDATE snapshots SET render_status = ?, render_path = ? WHERE id = ?",
                (status, render_path, snapshot_id),
            )
        await db.commit()


__all__ = ["render_plan", "RenderResult", "RenderError"]


# Annotations imports kept silent for ruff:
_ = Any
