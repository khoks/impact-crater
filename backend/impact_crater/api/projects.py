"""Projects API — list projects with their snapshots for the dashboard.

S-2.9.2: the M0 stub returned a hardcoded `[]`, so the dashboard showed
"No projects yet." forever even though projects + rendered snapshots sat
in SQLite — after a server restart there was no UI path back to a
finished render. This endpoint is the persistent complement to the
in-memory `GET /api/jobs` registry list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from impact_crater.storage.db import connection

router = APIRouter()


@router.get("")
async def list_projects() -> list[dict[str, Any]]:
    """All projects, newest first, each with its snapshots (newest first).

    `has_render` is true only when the render finished AND the file still
    exists on disk — a stale snapshots row must not produce a dead link.
    """
    async with connection() as db:
        cursor = await db.execute(
            "SELECT id, name, brief, created_at, updated_at FROM projects "
            "ORDER BY created_at DESC"
        )
        project_rows = await cursor.fetchall()
        cursor = await db.execute(
            "SELECT id, project_id, created_at, render_status, render_path "
            "FROM snapshots ORDER BY created_at DESC"
        )
        snapshot_rows = await cursor.fetchall()

    snaps_by_project: dict[str, list[dict[str, Any]]] = {}
    for s in snapshot_rows:
        render_path = s["render_path"]
        has_render = bool(
            s["render_status"] == "success"
            and render_path
            and Path(render_path).is_file()
        )
        snaps_by_project.setdefault(s["project_id"], []).append(
            {
                "id": s["id"],
                "created_at": s["created_at"],
                "render_status": s["render_status"],
                "has_render": has_render,
            }
        )

    return [
        {
            "id": p["id"],
            "name": p["name"],
            "brief": p["brief"] or "",
            "created_at": p["created_at"],
            "updated_at": p["updated_at"],
            "snapshots": snaps_by_project.get(p["id"], []),
        }
        for p in project_rows
    ]
