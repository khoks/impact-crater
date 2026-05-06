"""Profile API per N-010 + ADR-0014.

  GET  /api/profile/snapshot         — current Profile + JobSuggestions
  POST /api/profile/derive           — re-run derivation against the feedback log
  POST /api/profile/reset            — wipe profile + feedback log
  POST /api/profile/feedback         — emit a FeedbackEvent (used by the UI to
                                       record approve / refine / cancel etc.)
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from impact_crater import profile as profile_mod

router = APIRouter()


@router.get("/snapshot")
async def get_snapshot() -> dict[str, Any]:
    profile = profile_mod.load_profile()
    suggestions = profile_mod.suggestions_for_new_job(profile)
    return {
        "profile": asdict(profile),
        "suggestions": asdict(suggestions),
    }


@router.post("/derive")
async def post_derive() -> dict[str, Any]:
    p = profile_mod.derive_profile()
    profile_mod.save_profile(p)
    return {"derived_from_n_events": p.derived_from_n_events}


@router.post("/reset")
async def post_reset() -> dict[str, bool]:
    profile_mod.reset()
    return {"reset": True}


class FeedbackPayload(BaseModel):
    event_type: Literal[
        "approve",
        "refine",
        "second_guess_accepted",
        "second_guess_rejected",
        "second_guess_modified",
        "refinement_succeeded",
        "refinement_failed",
        "pre_filter_overridden",
        "effort_level_overridden",
        "publish_succeeded",
        "publish_failed",
        "job_cancelled",
    ]
    project_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/feedback")
async def post_feedback(req: FeedbackPayload) -> dict[str, bool]:
    profile_mod.emit(
        profile_mod.FeedbackEvent(
            event_type=req.event_type,
            project_id=req.project_id,
            snapshot_id=req.snapshot_id,
            payload=req.payload,
        )
    )
    return {"emitted": True}
