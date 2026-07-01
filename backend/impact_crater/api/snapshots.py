"""Snapshot artifact serving + refine endpoint.

  GET  /api/snapshots/{id}/render.mp4
  GET  /api/snapshots/{id}/cost_summary.json
  GET  /api/snapshots/{id}/plan.json
  GET  /api/snapshots/{id}/second_guess.json     (M6)
  POST /api/snapshots/{id}/refine                (M6 — N-009)

The frontend's preview UI (S-2.4.4) loads `render.mp4` from this path
into an HTML5 `<video>` element. CORS-safe because the frontend is
served from the same origin.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from impact_crater.pipeline import runner, stage6_plan
from impact_crater.pipeline.stage9_refine import execute_refinement
from impact_crater.storage.db import connection

router = APIRouter()


@router.get("/{snapshot_id}/render.mp4")
async def get_render(snapshot_id: str) -> FileResponse:
    """Serve the rendered MP4 for `snapshot_id`.

    `content_disposition_type="inline"` matters: the `filename=` parameter
    alone makes FileResponse emit `Content-Disposition: attachment`, and
    Chrome refuses to play attachment responses inside a <video> element —
    the player sits at readyState 0 forever (dashboard + JobPreview both
    stream this URL). Inline keeps the filename for save-as while letting
    the media stack render it.
    """
    path = await _resolve_render_path(snapshot_id)
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{snapshot_id}.mp4",
        content_disposition_type="inline",
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


@router.get("/{snapshot_id}/diagnostics")
async def get_diagnostics(snapshot_id: str) -> JSONResponse:
    """Per-phase decision diagnostics for the feedback loop (A-023)."""
    snap_dir = await _resolve_snapshot_dir(snapshot_id)
    candidate = snap_dir / "diagnostics.json"
    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "diagnostics.json not found — this snapshot predates the "
                "feedback-loop feature; re-run the job to generate it."
            ),
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


# ---- M6 endpoints ------------------------------------------------------


@router.get("/{snapshot_id}/second_guess.json")
async def get_second_guess(snapshot_id: str) -> JSONResponse:
    snap_dir = await _resolve_snapshot_dir(snapshot_id)
    candidate = snap_dir / "second_guess.json"
    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no second_guess.json (orchestrator had no overrides)",
        )
    return JSONResponse(json.loads(candidate.read_text(encoding="utf-8")))


class RefineRequest(BaseModel):
    refinement_message: str = Field(min_length=1, max_length=2000)


class RefineResponse(BaseModel):
    interpretation: str
    explanation: str | None
    new_snapshot_id: str | None
    rendered: bool
    reserve_destinations: list[str]
    has_directive_patch: bool
    brief_addendum: str | None


@router.post("/{snapshot_id}/refine", response_model=RefineResponse)
async def post_refine(snapshot_id: str, req: RefineRequest) -> RefineResponse:
    """Open-ended agentic refinement (E-2.12). Interprets the free-text request
    against the snapshot's plan + analysis, applies the shared levers
    (PlanDirective pacing / destination reservation / narrative re-judge), and
    renders a **child snapshot**. Returns the interpretation + new snapshot id.
    """
    project_id = await _resolve_project_id(snapshot_id)
    try:
        prior_plan = stage6_plan.load_plan(snapshot_id, project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan.json missing") from exc

    try:
        llm_router = await runner.build_router_from_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED, detail=str(exc)
        ) from exc

    result = await execute_refinement(
        llm_router,
        project_id=project_id,
        prior_plan=prior_plan,
        refinement_message=req.refinement_message,
    )

    snap_dir = await _resolve_snapshot_dir(snapshot_id)
    (snap_dir / "refinement_plan.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")

    o = result.outcome
    return RefineResponse(
        interpretation=o.interpretation,
        explanation=o.explanation,
        new_snapshot_id=result.new_snapshot_id,
        rendered=result.rendered,
        reserve_destinations=o.reserve_destinations,
        has_directive_patch=o.directive_patch is not None,
        brief_addendum=o.brief_addendum,
    )


async def _resolve_project_id(snapshot_id: str) -> str:
    async with connection() as db:
        cursor = await db.execute("SELECT project_id FROM snapshots WHERE id = ?", (snapshot_id,))
        row = await cursor.fetchone()
    if row is None or not row["project_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"snapshot {snapshot_id!r} not found"
        )
    return str(row["project_id"])
