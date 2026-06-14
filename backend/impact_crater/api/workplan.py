"""Workplan tracker API (A-024).

Surfaces the in-repo four-level work hierarchy (project/initiatives, epics,
stories, tasks) — the MVP/v1/v2/v3 plan maintained since project start — as
a queryable tree the in-app workplan page renders with status + phase +
priority.

The project/ markdown is the canonical source of truth (and the
work-tracker skill is its only writer, via PRs). So this API READS the
markdown but never writes it; priority changes from the page are stored as
`workplan_overrides` rows and surfaced for a later session to reconcile
into the markdown. The page shows the effective priority (override if set,
else the markdown's).

In a packaged install where project/ isn't shipped, the endpoints return an
empty plan rather than erroring.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from impact_crater.storage.db import connection

log = logging.getLogger(__name__)

router = APIRouter()

_LEVEL_DIRS = ["initiatives", "epics", "stories", "tasks"]


def _project_dir() -> Path | None:
    override = os.environ.get("IMPACT_CRATER_PROJECT_DIR")
    if override:
        p = Path(override)
        return p if p.is_dir() else None
    # backend/impact_crater/api/workplan.py → parents[3] == repo root (dev /
    # editable install). Packaged installs won't have project/ — return None.
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "project"
    return candidate if candidate.is_dir() else None


class WorkItem(BaseModel):
    id: str
    title: str
    type: str  # initiative | epic | story | task
    status: str
    phase: str
    priority: str  # effective (override if present, else markdown)
    markdown_priority: str
    priority_overridden: bool
    parent: str | None = None
    updated: str | None = None
    tags: list[str] = Field(default_factory=list)
    override_note: str | None = None


class WorkplanResponse(BaseModel):
    items: list[WorkItem]
    available: bool  # False when project/ isn't on disk (packaged install)
    counts_by_status: dict[str, int]
    counts_by_phase: dict[str, int]


class WorkplanPatch(BaseModel):
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    note: str | None = Field(default=None, max_length=2000)


def _read_frontmatter(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        log.debug("workplan: bad frontmatter in %s: %s", path.name, exc)
        return None
    return data if isinstance(data, dict) else None


async def _overrides() -> dict[str, dict[str, Any]]:
    async with connection() as db:
        rows = await (
            await db.execute("SELECT item_id, priority, note FROM workplan_overrides")
        ).fetchall()
    return {r["item_id"]: {"priority": r["priority"], "note": r["note"]} for r in rows}


@router.get("", response_model=WorkplanResponse)
async def get_workplan() -> WorkplanResponse:
    """The full work hierarchy with effective priorities + rollup counts."""
    proj = _project_dir()
    if proj is None:
        return WorkplanResponse(
            items=[], available=False, counts_by_status={}, counts_by_phase={}
        )

    overrides = await _overrides()
    items: list[WorkItem] = []
    for level in _LEVEL_DIRS:
        d = proj / level
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            fm = _read_frontmatter(f)
            if not fm or "id" not in fm:
                continue
            item_id = str(fm["id"])
            md_priority = str(fm.get("priority") or "P2")
            ov = overrides.get(item_id)
            eff_priority = (ov["priority"] if ov and ov["priority"] else None) or md_priority
            tags_val = fm.get("tags") or []
            items.append(
                WorkItem(
                    id=item_id,
                    title=str(fm.get("title") or item_id),
                    type=str(fm.get("type") or level[:-1]),
                    status=str(fm.get("status") or "todo"),
                    phase=str(fm.get("phase") or "unknown"),
                    priority=eff_priority,
                    markdown_priority=md_priority,
                    priority_overridden=bool(ov and ov["priority"]),
                    parent=str(fm["parent"]) if fm.get("parent") else None,
                    updated=str(fm["updated"]) if fm.get("updated") else None,
                    tags=[str(t) for t in tags_val] if isinstance(tags_val, list) else [],
                    override_note=ov["note"] if ov else None,
                )
            )

    counts_by_status: dict[str, int] = {}
    counts_by_phase: dict[str, int] = {}
    for it in items:
        counts_by_status[it.status] = counts_by_status.get(it.status, 0) + 1
        counts_by_phase[it.phase] = counts_by_phase.get(it.phase, 0) + 1

    return WorkplanResponse(
        items=items,
        available=True,
        counts_by_status=counts_by_status,
        counts_by_phase=counts_by_phase,
    )


@router.patch("/{item_id}")
async def patch_workplan_item(item_id: str, patch: WorkplanPatch) -> dict[str, Any]:
    """Set a priority override (and/or note) for a work item. Stored in the
    DB, NOT the markdown — a later work-tracker run reconciles it into the
    canonical project/ file."""
    if patch.priority is None and patch.note is None:
        raise HTTPException(status_code=400, detail="nothing to update")
    async with connection() as db:
        await db.execute(
            """
            INSERT INTO workplan_overrides (item_id, priority, note, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                priority = COALESCE(excluded.priority, workplan_overrides.priority),
                note = COALESCE(excluded.note, workplan_overrides.note),
                updated_at = CURRENT_TIMESTAMP
            """,
            (item_id, patch.priority, patch.note),
        )
        await db.commit()
    log.info("workplan_override item=%s priority=%s", item_id, patch.priority)
    return {"item_id": item_id, "priority": patch.priority, "note": patch.note}


@router.get("/overrides")
async def list_overrides() -> list[dict[str, Any]]:
    """Pending priority overrides for a Claude session to reconcile into the
    canonical project/ markdown."""
    async with connection() as db:
        rows = await (
            await db.execute(
                "SELECT item_id, priority, note, updated_at FROM workplan_overrides "
                "ORDER BY updated_at DESC"
            )
        ).fetchall()
    return [dict(r) for r in rows]
