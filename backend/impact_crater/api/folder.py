"""GET /api/folder/scan — recursively list supported media in a folder.

Per ADR-0010, photos = JPEG/PNG/WebP/AVIF/HEIC/HEIF/RAW; videos = MP4/MOV/etc.
The frontend uses this to confirm a user-entered folder path before
submitting a job (browsers can't expose absolute filesystem paths in
drag-drop, so we accept a path string + scan server-side).

Symlink-walk-out-of-root is rejected to keep the surface honest about
what's actually inside the folder the user typed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from impact_crater.pipeline.stage1_ingest import _PHOTO_EXTS, _VIDEO_EXTS

router = APIRouter()

# Hard cap on how much we'll walk in one request — anything larger means
# the user picked a wrong folder. The MVP scale envelope is 1000 photos
# + 50 videos; 5000 entries is a comfortable ceiling.
_MAX_ENTRIES = 5000


class FolderScanItem(BaseModel):
    path: str
    media_type: str  # "photo" | "video"
    file_size: int


class FolderScanResponse(BaseModel):
    folder: str
    items: list[FolderScanItem]
    photo_count: int
    video_count: int
    total_bytes: int
    truncated: bool = False


@dataclass
class _ScanCounts:
    items: list[FolderScanItem]
    photos: int = 0
    videos: int = 0
    bytes_: int = 0
    truncated: bool = False


@router.get("/scan", response_model=FolderScanResponse)
async def scan(path: str) -> FolderScanResponse:
    """Walk `path` (a server-side directory) and list supported media files."""
    p = Path(path).expanduser()
    if not p.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"path does not exist: {path}",
        )
    if not p.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"path is not a directory: {path}",
        )

    p = p.resolve()
    counts = _ScanCounts(items=[])

    for entry in _walk_supported(p):
        # Reject symlinks that escape the original root.
        try:
            real = entry.resolve()
            real.relative_to(p)
        except (OSError, ValueError):
            continue
        media_type = _classify(entry)
        if media_type is None:
            continue
        try:
            size = entry.stat().st_size
        except OSError:
            continue
        counts.items.append(
            FolderScanItem(path=str(entry), media_type=media_type, file_size=size)
        )
        if media_type == "photo":
            counts.photos += 1
        else:
            counts.videos += 1
        counts.bytes_ += size
        if len(counts.items) >= _MAX_ENTRIES:
            counts.truncated = True
            break

    return FolderScanResponse(
        folder=str(p),
        items=counts.items,
        photo_count=counts.photos,
        video_count=counts.videos,
        total_bytes=counts.bytes_,
        truncated=counts.truncated,
    )


def _walk_supported(root: Path):
    """Yield files under `root` whose suffix is photo/video."""
    yield from (
        e
        for e in root.rglob("*")
        if e.is_file() and e.suffix.lower() in (_PHOTO_EXTS | _VIDEO_EXTS)
    )


def _classify(p: Path) -> str | None:
    ext = p.suffix.lower()
    if ext in _PHOTO_EXTS:
        return "photo"
    if ext in _VIDEO_EXTS:
        return "video"
    return None
