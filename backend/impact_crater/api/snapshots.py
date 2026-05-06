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
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from impact_crater.llm_clients.base import ArcJudgment, CandidateRef, SelectedItem
from impact_crater.pipeline import runner
from impact_crater.pipeline.stage4_prefilter import CandidateSet
from impact_crater.pipeline.stage9_refine import refine as run_refine
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
    strategy: str
    rationale: str
    explanation: str | None
    brief_addendum: str | None
    new_arc_judgment: dict[str, Any] | None
    turns_used: int


@router.post("/{snapshot_id}/refine", response_model=RefineResponse)
async def post_refine(snapshot_id: str, req: RefineRequest) -> RefineResponse:
    """Run the M6 N-009 thinking step over a snapshot's prior plan + the
    user's free-text refinement message. Returns the chosen strategy +
    (when applicable) a new ArcJudgment.

    M6 baseline: synchronous + thinking-step-only. The full re-render of
    Stages 6-7 with the new ArcJudgment is a v1 follow-up.
    """
    snap_dir = await _resolve_snapshot_dir(snapshot_id)
    plan_path = snap_dir / "plan.json"
    if not plan_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="plan.json missing"
        )
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    arc_reasoning = plan_data.get("arc_reasoning", "")
    arc_confidence = float(plan_data.get("arc_confidence", 0.5))
    target_duration = int(plan_data.get("target_duration_ms", 60000)) // 1000
    mode = plan_data.get("mode", "standard")
    # Reconstruct a minimal ArcJudgment + CandidateSet from the plan's clips.
    selected_items = [
        SelectedItem(
            candidate_ref=c["candidate_ref"],
            placement_position=i,
            intended_duration_ms=int(c["intended_duration_ms"]),
            role=c.get("role", ""),
            notes=c.get("notes", ""),
        )
        for i, c in enumerate(plan_data.get("clips", []))
    ]
    prior_arc = ArcJudgment(
        selected_items=selected_items,
        arc_reasoning=arc_reasoning,
        confidence=arc_confidence,
    )
    candidate_set = CandidateSet(
        items=[
            CandidateRef(
                content_hash=c["candidate_ref"].split("#", 1)[0],
                scene_index=int(c["candidate_ref"].split("#", 1)[1])
                if "#" in c["candidate_ref"]
                else None,
                quality_score=None,
                narrative_relevance=None,
            )
            for c in plan_data.get("clips", [])
        ],
        cluster_metadata={"input_count": len(plan_data.get("clips", []))},
        filter_log=[],
        target_size=len(plan_data.get("clips", [])),
        floor=1,
        ceiling=len(plan_data.get("clips", [])),
    )

    # Build a router from settings.
    try:
        llm_router = await runner.build_router_from_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED, detail=str(exc)
        ) from exc

    # Brief is not persisted on plan.json today; use an empty placeholder.
    # v1: the runner persists the brief on the snapshot for reuse here.
    brief = plan_data.get("brief", arc_reasoning or "(no brief recorded)")

    result = await run_refine(
        router=llm_router,
        prior_arc=prior_arc,
        candidate_set=candidate_set,
        refinement_message=req.refinement_message,
        brief=brief,
        target_duration_seconds=target_duration,
        mode=mode if mode in ("standard", "music_video") else "standard",
    )

    # Persist the refinement_plan.json on the snapshot per ADR-0011.
    refinement_path = snap_dir / "refinement_plan.json"
    refinement_path.write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )

    return RefineResponse(
        strategy=result.plan.strategy,
        rationale=result.plan.rationale,
        explanation=result.plan.explanation,
        brief_addendum=result.plan.brief_addendum,
        new_arc_judgment=asdict(result.arc_judgment) if result.arc_judgment else None,
        turns_used=result.turns_used,
    )


_ = Any
