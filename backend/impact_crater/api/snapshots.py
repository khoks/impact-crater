"""Snapshot artifact serving — `GET /api/snapshots/{snapshot_id}/render.mp4`
+ `/cost_summary.json` + `/plan.json`.

The frontend's preview UI (S-2.4.4) loads `render.mp4` from this path
into an HTML5 `<video>` element. CORS-safe because the frontend is
served from the same origin.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse

from impact_crater.storage.db import connection

router = APIRouter()


@router.get("/{snapshot_id}/render.mp4")
async def get_render(snapshot_id: str) -> FileResponse:
    """Serve the rendered MP4 for `snapshot_id`."""
    path = await _resolve_render_path(snapshot_id)
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{snapshot_id}.mp4",
    )


@router.get("/{snapshot_id}/cost_summary.json")
async def get_cost_summary(snapshot_id: str) -> JSONResponse:
    snap_dir = await _resolve_snapshot_dir(snapshot_id)
    candidate = snap_dir / "cost_summary.json"
    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cost_summary.json not found for snapshot {snapshot_id!r}",
        )
    return JSONResponse(json.loads(candidate.read_text(encoding="utf-8")))


@router.get("/{snapshot_id}/plan.json")
async def get_plan(snapshot_id: str) -> JSONResponse:
    snap_dir = await _resolve_snapshot_dir(snapshot_id)
    candidate = snap_dir / "plan.json"
    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"plan.json not found for snapshot {snapshot_id!r}",
        )
    return JSONResponse(json.loads(candidate.read_text(encoding="utf-8")))


# ---- Internal ----------------------------------------------------------


async def _resolve_render_path(snapshot_id: str) -> Path:
    async with connection() as db:
        cursor = await db.execute(
            "SELECT render_path FROM snapshots WHERE id = ?", (snapshot_id,)
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"snapshot {snapshot_id!r} not found",
        )
    if not row["render_path"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"snapshot {snapshot_id!r} has no rendered MP4 yet",
        )
    p = Path(row["render_path"])
    if not p.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"render file missing on disk: {p}",
        )
    return p


async def _resolve_snapshot_dir(snapshot_id: str) -> Path:
    async with connection() as db:
        cursor = await db.execute(
            "SELECT plan_path FROM snapshots WHERE id = ?", (snapshot_id,)
        )
        row = await cursor.fetchone()
    if row is None or not row["plan_path"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"snapshot {snapshot_id!r} not found",
        )
    return Path(row["plan_path"]).parent


_ = Any
