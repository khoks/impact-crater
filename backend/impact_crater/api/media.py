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

from fastapi import APIRouter, HTTPException, status
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


@router.get("/{content_hash}/thumb.jpg")
async def get_media_thumb(content_hash: str) -> FileResponse:
    """Serve the thumbnail for a media content hash."""
    if not _HASH_RE.match(content_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid content hash")
    path = _find_thumb(content_hash)
    if path is None or not Path(path).is_file():
        # Bust a stale cache entry and report cleanly (videos have no photo
        # thumbnail; the UI falls back to a placeholder).
        _find_thumb.cache_clear()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no thumbnail for {content_hash}",
        )
    return FileResponse(path, media_type="image/jpeg", content_disposition_type="inline")
