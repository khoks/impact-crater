"""Media thumbnail serving for the diagnostics UI (A-023).

The feedback-loop diagnostics reference media by `content_hash`; the UI
needs a thumbnail to show what each decision was about. Thumbnails are
written per project under `{project}/cache/thumbs/{hash}.256.jpg`, but a
content hash can be shared across projects, so we resolve by globbing the
projects tree and serving the first match.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from impact_crater import paths

router = APIRouter()

_HASH_RE = re.compile(r"^[a-f0-9]{16,64}$")


@lru_cache(maxsize=2048)
def _find_thumb(content_hash: str) -> str | None:
    """Locate a 256px thumbnail for `content_hash` across all projects.
    Cached — thumbnails are immutable once written."""
    root = paths.projects_dir()
    if not root.is_dir():
        return None
    for size in ("256", "1024"):
        for match in root.glob(f"*/cache/thumbs/{content_hash}.{size}.jpg"):
            if match.is_file():
                return str(match)
    return None


@lru_cache(maxsize=4096)
def _find_scene_frame(content_hash: str, scene_index: int) -> str | None:
    """Locate a Stage-1 representative frame for a video scene (F8b).
    Video scenes have no photo thumbnail; the inspect UI needs the extracted
    frame so video keep/drop/select decisions are reviewable."""
    root = paths.projects_dir()
    if not root.is_dir():
        return None
    for label in ("middle", "start", "end"):
        for match in root.glob(
            f"*/cache/scenes/{content_hash}/scene-{scene_index}-{label}.png"
        ):
            if match.is_file():
                return str(match)
    return None


@router.get("/{content_hash}/thumb.jpg")
async def get_media_thumb(
    content_hash: str, scene: int | None = Query(default=None)
) -> FileResponse:
    """Serve the thumbnail for a media content hash. With `?scene=N`, serve the
    extracted representative frame for that video scene (F8b)."""
    if not _HASH_RE.match(content_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid content hash")
    if scene is not None:
        frame = _find_scene_frame(content_hash, scene)
        if frame is not None and Path(frame).is_file():
            return FileResponse(frame, media_type="image/png", content_disposition_type="inline")
        _find_scene_frame.cache_clear()
        # Fall through to a photo thumb (ref may be mis-tagged), else 404 below.
    path = _find_thumb(content_hash)
    if path is None or not Path(path).is_file():
        # Bust a stale cache entry and report cleanly.
        _find_thumb.cache_clear()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no thumbnail for {content_hash}",
        )
    return FileResponse(path, media_type="image/jpeg", content_disposition_type="inline")
