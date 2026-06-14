"""Stage 1 — ingest + content-hash + scene-segment + thumbnails per ADR-0010 + ADR-0011.

Inputs: a project_id + a list of source media paths.
Outputs: media SQLite rows (and project_media join rows), source sidecars,
thumbnails (256/1024 px JPEG), and per-video scenes.json + representative frames.

Photo decode: Pillow + pillow-heif. Video decode: OpenCV (via scenedetect's
default backend) for scene segmentation and probing. ffmpeg is not required
at Stage 1 — it is required for Stage 7 render (later epic).

The function is **idempotent**: running it twice on the same paths is a
no-op for already-ingested content (ON CONFLICT IGNORE on the media row).
The cache and project_media join row are kept in sync regardless.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# Register HEIF codec for Pillow before any image-open call.
try:  # pragma: no cover — env-specific
    from pillow_heif import register_heif_opener  # type: ignore[import-not-found]

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

import imagehash
from PIL import Image, ImageOps

from impact_crater import paths
from impact_crater.media import timeline
from impact_crater.storage.db import connection
from impact_crater.workers import WorkerPool, default_pool

log = logging.getLogger(__name__)


# ---- Types -------------------------------------------------------------


MediaType = Literal["photo", "video"]


@dataclass
class SceneRecord:
    index: int
    start_seconds: float
    end_seconds: float
    representative_frame_paths: list[str]  # 3 paths


@dataclass
class MediaRecord:
    content_hash: str
    source_path: str
    media_type: MediaType
    file_size: int
    quick_stats: dict[str, Any]
    thumb_256_path: str | None = None
    thumb_1024_path: str | None = None
    scenes: list[SceneRecord] | None = None  # videos only
    # Chronology (A-021): capture time reconciled across EXIF / filename /
    # mtime, plus its source + confidence so the planner can weigh it.
    capture_timestamp: str | None = None  # ISO 8601
    capture_source: str | None = None  # "exif" / "filename" / "file_mtime" / "none"
    capture_confidence: float = 0.0
    gps_lat: float | None = None
    gps_lon: float | None = None


_PHOTO_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".avif",
    ".heic",
    ".heif",
    ".bmp",
    ".tif",
    ".tiff",
}
_VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
    ".mts",
    ".m2ts",
    ".3gp",
}

# Per ADR-0010 — scene cap per video; user-overridable later via settings.
_DEFAULT_SCENE_CAP = 50
# Per ADR-0010 — 3 representative frames per scene (start, middle, end).
_FRAMES_PER_SCENE = 3
# A-016 time-bounded sampling: a single long take (e.g. a 60s pan) would
# otherwise be ONE scene summarized by 3 frames — badly under-sampled.
# Subdivide any detected scene longer than _MAX_SCENE_SECONDS into
# sub-scenes of ~_TARGET_SUBSCENE_SECONDS so each stretch gets its own
# metadata and becomes its own candidate.
_MAX_SCENE_SECONDS = 12.0
_TARGET_SUBSCENE_SECONDS = 8.0


# ---- Public API --------------------------------------------------------


async def ingest_media(
    project_id: str,
    media_paths: list[Path],
    *,
    pool: WorkerPool | None = None,
    scene_cap: int = _DEFAULT_SCENE_CAP,
) -> list[MediaRecord]:
    """Ingest every path in `media_paths` into the project.

    Photos: hash + decode + pHash/dHash + thumbnails.
    Videos: hash + cv2-probe + scene-detect + per-scene representative frames.

    Heavy lifting runs on the worker pool's `cpu` class so the caller can
    parallelize many paths and still respect the per-class cap.
    """
    pool = pool or default_pool()
    out = await pool.submit_many(
        "cpu",
        media_paths,
        lambda path: _ingest_one(project_id, path, scene_cap=scene_cap),
    )
    # Drop None entries (e.g., unrecognized format) and return the rest.
    return [m for m in out if m is not None]


# ---- Single-path workhorse ---------------------------------------------


async def _ingest_one(
    project_id: str,
    path: Path,
    *,
    scene_cap: int,
) -> MediaRecord | None:
    if not path.is_file():
        log.warning("ingest: path missing: %s", path)
        return None
    media_type = _classify(path)
    if media_type is None:
        log.info("ingest: unrecognized format, skipping: %s", path)
        return None

    content_hash = await asyncio.to_thread(_sha256_file, path)
    file_size = path.stat().st_size

    if media_type == "photo":
        record = await asyncio.to_thread(
            _ingest_photo, project_id, path, content_hash, file_size
        )
    else:
        record = await asyncio.to_thread(
            _ingest_video,
            project_id,
            path,
            content_hash,
            file_size,
            scene_cap,
        )

    await _persist(project_id, record)
    return record


# ---- Photo ingest ------------------------------------------------------


def _ingest_photo(
    project_id: str,
    path: Path,
    content_hash: str,
    file_size: int,
) -> MediaRecord:
    img = Image.open(path)
    # Apply the EXIF orientation tag to the pixels. Phone photos shot in
    # portrait are stored landscape + Orientation=6/8 — without this,
    # width/height (and so Stage 6's aspect decision), the pHash, and the
    # thumbnails fed to the vision LLMs are all sideways. Real failure
    # 2026-06-11: 3 of 33 Zion photos rendered pillarboxed-sideways.
    img = ImageOps.exif_transpose(img)
    img = _to_rgb(img)
    width, height = img.size
    phash_hex = str(imagehash.phash(img))
    dhash_hex = str(imagehash.dhash(img))

    project_cache = paths.projects_dir() / project_id / "cache" / "thumbs"
    project_cache.mkdir(parents=True, exist_ok=True)
    thumb_256 = project_cache / f"{content_hash}.256.jpg"
    thumb_1024 = project_cache / f"{content_hash}.1024.jpg"
    _write_thumbnail(img, thumb_256, max_dim=256)
    _write_thumbnail(img, thumb_1024, max_dim=1024)

    quick_stats = {
        "width": width,
        "height": height,
        "phash": phash_hex,
        "dhash": dhash_hex,
    }
    ct = timeline.extract_capture_time(path, is_photo=True)
    gps = timeline.extract_gps(path, is_photo=True)
    return MediaRecord(
        content_hash=content_hash,
        source_path=str(path),
        media_type="photo",
        file_size=file_size,
        quick_stats=quick_stats,
        thumb_256_path=str(thumb_256),
        thumb_1024_path=str(thumb_1024),
        capture_timestamp=ct.iso,
        capture_source=ct.source,
        capture_confidence=ct.confidence,
        gps_lat=gps.lat if gps else None,
        gps_lon=gps.lon if gps else None,
    )


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    return img.convert("RGB")


def _write_thumbnail(img: Image.Image, dest: Path, *, max_dim: int) -> None:
    thumb = img.copy()
    thumb.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    thumb.save(dest, format="JPEG", quality=85)


# ---- Video ingest ------------------------------------------------------


def _ingest_video(
    project_id: str,
    path: Path,
    content_hash: str,
    file_size: int,
    scene_cap: int,
) -> MediaRecord:
    """cv2-probe + scenedetect.

    cv2 reads the video metadata (width/height/fps/frame-count → duration)
    without invoking ffmpeg. scenedetect's ContentDetector then segments
    the video and we extract 3 representative frames per scene.
    """
    import cv2  # local import — cv2 can be slow to import

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cv2 could not open video: {path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_seconds = (frame_count / fps) if fps > 0 else 0.0
    cap.release()

    scene_dir = paths.projects_dir() / project_id / "cache" / "scenes" / content_hash
    scene_dir.mkdir(parents=True, exist_ok=True)

    scenes = _detect_scenes(path, scene_dir, scene_cap=scene_cap)

    # Persist scenes.json sidecar for resume + Stage 2 consumption.
    (scene_dir / "scenes.json").write_text(
        json.dumps(
            [
                {
                    "index": s.index,
                    "start_seconds": s.start_seconds,
                    "end_seconds": s.end_seconds,
                    "representative_frame_paths": s.representative_frame_paths,
                }
                for s in scenes
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    quick_stats = {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration_seconds,
        "frame_count": frame_count,
        "scene_count": len(scenes),
    }
    ct = timeline.extract_capture_time(path, is_photo=False)
    return MediaRecord(
        content_hash=content_hash,
        source_path=str(path),
        media_type="video",
        file_size=file_size,
        quick_stats=quick_stats,
        scenes=scenes,
        capture_timestamp=ct.iso,
        capture_source=ct.source,
        capture_confidence=ct.confidence,
    )


def _detect_scenes(
    path: Path,
    scene_dir: Path,
    *,
    scene_cap: int,
) -> list[SceneRecord]:
    """Run scenedetect ContentDetector + extract 3 representative frames per scene.

    Falls back to a single "whole video" scene if scenedetect produces zero
    cuts (typical for a synthetic test video).
    """
    import cv2
    from scenedetect import ContentDetector, detect

    try:
        scene_list = detect(str(path), ContentDetector())
    except Exception as exc:
        log.warning("scenedetect failed for %s: %s; treating as single scene", path, exc)
        scene_list = []

    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = (frame_count / fps) if fps > 0 else 0.0

    if not scene_list:
        # Single-scene fallback: cover the whole video.
        scene_list = [_pseudo_scene(0.0, duration, fps, frame_count)]

    # Convert to (start_s, end_s) bounds, then subdivide long takes so a
    # single 60s scene isn't summarized by 3 frames (A-016).
    bounds = [_scene_bounds(sc) for sc in scene_list]
    bounds = _subdivide_long_scenes(bounds)

    if len(bounds) > scene_cap:
        bounds = bounds[:scene_cap]

    out: list[SceneRecord] = []
    for i, (start_s, end_s) in enumerate(bounds):
        frames = _extract_frames(cap, fps, start_s, end_s, scene_dir, i)
        out.append(
            SceneRecord(
                index=i,
                start_seconds=start_s,
                end_seconds=end_s,
                representative_frame_paths=[str(p) for p in frames],
            )
        )
    cap.release()
    return out


def _subdivide_long_scenes(
    bounds: list[tuple[float, float]],
    *,
    max_len: float = _MAX_SCENE_SECONDS,
    target_len: float = _TARGET_SUBSCENE_SECONDS,
) -> list[tuple[float, float]]:
    """Split any (start, end) longer than `max_len` into near-equal
    sub-intervals of ~`target_len` so long takes are sampled densely."""
    out: list[tuple[float, float]] = []
    for start_s, end_s in bounds:
        dur = end_s - start_s
        if dur <= max_len:
            out.append((start_s, end_s))
            continue
        parts = max(2, math.ceil(dur / target_len))
        step = dur / parts
        for k in range(parts):
            a = start_s + k * step
            b = end_s if k == parts - 1 else start_s + (k + 1) * step
            out.append((a, b))
    return out


def _pseudo_scene(start_s: float, end_s: float, fps: float, frame_count: int) -> tuple:
    """Produce a (start_timecode, end_timecode) pair compatible with scenedetect output."""
    from scenedetect import FrameTimecode

    start = FrameTimecode(start_s, fps if fps > 0 else 30.0)
    end = FrameTimecode(end_s, fps if fps > 0 else 30.0)
    return (start, end)


def _scene_bounds(scene: tuple) -> tuple[float, float]:
    """scenedetect yields (start_timecode, end_timecode) tuples."""
    start, end = scene
    # scenedetect 0.7 exposes `.seconds`; older versions had get_seconds().
    if hasattr(start, "seconds"):
        return (float(start.seconds), float(end.seconds))
    if hasattr(start, "get_seconds"):
        return (float(start.get_seconds()), float(end.get_seconds()))
    return (float(start), float(end))


def _extract_frames(
    cap: Any,
    fps: float,
    start_s: float,
    end_s: float,
    scene_dir: Path,
    scene_index: int,
) -> list[Path]:
    import cv2

    if fps <= 0:
        fps = 30.0
    midpoint = (start_s + end_s) / 2.0
    targets = [
        ("start", start_s),
        ("middle", midpoint),
        # Pull the 'end' frame slightly before the cut to avoid black frames.
        ("end", max(start_s, end_s - (1.0 / max(fps, 1.0)))),
    ]
    out_paths: list[Path] = []
    for label, t in targets:
        out = scene_dir / f"scene-{scene_index}-{label}.png"
        frame_index = max(0, int(t * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            # Try the very first frame as a fallback.
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if ok and frame is not None:
            cv2.imwrite(str(out), frame)
            out_paths.append(out)
    return out_paths


# ---- Format detection + hashing ---------------------------------------


def _classify(path: Path) -> MediaType | None:
    ext = path.suffix.lower()
    if ext in _PHOTO_EXTS:
        return "photo"
    if ext in _VIDEO_EXTS:
        return "video"
    return None


def _sha256_file(path: Path) -> str:
    """Stream-hash the file in 1MB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---- Persistence -------------------------------------------------------


async def _persist(project_id: str, record: MediaRecord) -> None:
    """Upsert media + project_media + write the source sidecar JSON.

    Idempotent: ON CONFLICT IGNORE on `media`, ON CONFLICT IGNORE on
    `project_media`. Re-ingesting refreshes the sidecar (which is cheap).
    """
    sources_dir = paths.projects_dir() / project_id / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = sources_dir / f"{record.content_hash}.json"
    sidecar_payload = {
        "content_hash": record.content_hash,
        "source_path": record.source_path,
        "media_type": record.media_type,
        "file_size": record.file_size,
        "quick_stats": record.quick_stats,
        "thumb_256_path": record.thumb_256_path,
        "thumb_1024_path": record.thumb_1024_path,
        "capture_timestamp": record.capture_timestamp,
        "capture_source": record.capture_source,
        "capture_confidence": record.capture_confidence,
        "gps_lat": record.gps_lat,
        "gps_lon": record.gps_lon,
        "scenes": [
            {
                "index": s.index,
                "start_seconds": s.start_seconds,
                "end_seconds": s.end_seconds,
                "representative_frame_paths": s.representative_frame_paths,
            }
            for s in (record.scenes or [])
        ],
    }
    sidecar_path.write_text(json.dumps(sidecar_payload, indent=2), encoding="utf-8")

    async with connection() as db:
        # Upsert (not INSERT OR IGNORE): a media row may already exist from
        # a pre-chronology ingest with NULL capture columns. Backfill them
        # on re-ingest via COALESCE so the persisted timeline catches up
        # without ever clobbering a known value with NULL.
        await db.execute(
            """
            INSERT INTO media
                (content_hash, source_path, media_type, file_size, quick_stats_json,
                 capture_timestamp, capture_source, capture_confidence, gps_lat, gps_lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(content_hash) DO UPDATE SET
                capture_timestamp  = COALESCE(excluded.capture_timestamp, media.capture_timestamp),
                capture_source     = COALESCE(excluded.capture_source, media.capture_source),
                capture_confidence = MAX(excluded.capture_confidence, media.capture_confidence),
                gps_lat            = COALESCE(excluded.gps_lat, media.gps_lat),
                gps_lon            = COALESCE(excluded.gps_lon, media.gps_lon)
            """,
            (
                record.content_hash,
                record.source_path,
                record.media_type,
                record.file_size,
                json.dumps(record.quick_stats),
                record.capture_timestamp,
                record.capture_source,
                record.capture_confidence,
                record.gps_lat,
                record.gps_lon,
            ),
        )
        # Even when the media row already exists, we may need to add a
        # join row for a *different* project consuming the same content.
        await db.execute(
            """
            INSERT OR IGNORE INTO projects (id, name)
            VALUES (?, ?)
            """,
            (project_id, project_id),
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO project_media (project_id, content_hash)
            VALUES (?, ?)
            """,
            (project_id, record.content_hash),
        )
        await db.commit()
