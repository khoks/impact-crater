"""GET /api/effort-levels + POST /api/jobs/cost-preview per D-013 + ADR-0015.

Effort levels are pre-canned envelopes (L1/L2/L3 for MVP per ADR-0015):
  L1 ≈ 10 photos / 1 video / $0.50–$2
  L2 ≈ 100 photos / 10 videos / $2–$7
  L3 ≈ 1000 photos / 50 videos / $7–$22 (the ADR-0009 per-job envelope)

`fits_today_budget` is computed per-level against the live `quota_state`
+ the user's spend caps. The agentic max-permissible recommendation
prose lands in v1; M3 only surfaces the bool + the per-level envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from impact_crater import quota

router = APIRouter()


@dataclass(frozen=True)
class _Level:
    id: str
    label: str
    photo_cap: int
    video_cap: int
    estimated_cost_usd_low: float
    estimated_cost_usd_high: float
    description: str


# Per ADR-0015 §"Effort levels (D-013 MVP)".
_LEVELS: list[_Level] = [
    _Level(
        id="L1",
        label="L1 — Quick highlights",
        photo_cap=10,
        video_cap=1,
        estimated_cost_usd_low=0.50,
        estimated_cost_usd_high=2.00,
        description="A handful of standout shots; one short video. Cheapest.",
    ),
    _Level(
        id="L2",
        label="L2 — Balanced recap",
        photo_cap=100,
        video_cap=10,
        estimated_cost_usd_low=2.00,
        estimated_cost_usd_high=7.00,
        description="Curated recap of an event. Mid-tier cost.",
    ),
    _Level(
        id="L3",
        label="L3 — Full curation",
        photo_cap=1000,
        video_cap=50,
        estimated_cost_usd_low=7.00,
        estimated_cost_usd_high=22.00,
        description="Full MVP envelope (~1000 photos + 50 videos). Highest cost.",
    ),
]


class EffortLevel(BaseModel):
    id: str
    label: str
    photo_cap: int
    video_cap: int
    estimated_cost_usd_low: float
    estimated_cost_usd_high: float
    description: str
    fits_today_budget: bool


class EffortLevelsResponse(BaseModel):
    levels: list[EffortLevel]
    today_total_spent_usd: float
    today_per_provider_spent_usd: dict[str, float]
    cap_total_usd: float | None
    cap_per_provider_usd: dict[str, float]
    recommended_level_id: str | None  # the highest level whose high-end fits


@router.get("/effort-levels", response_model=EffortLevelsResponse)
async def get_effort_levels() -> EffortLevelsResponse:
    """Return all 3 levels with `fits_today_budget` and the recommended L_max."""
    cap_total = await quota._read_total_cap()
    cap_per_provider = await quota._read_per_provider_caps()
    today = await quota.get_today_spend()
    spent_total = float(today.get("_total_", 0.0))
    spent_per_provider = {k: v for k, v in today.items() if k != "_total_"}

    out_levels: list[EffortLevel] = []
    for lvl in _LEVELS:
        fits = True
        if cap_total is not None:
            if spent_total + lvl.estimated_cost_usd_high > cap_total:
                fits = False
        else:
            fits = False  # No cap configured → fail-safe per quota.check_quota
        out_levels.append(
            EffortLevel(
                id=lvl.id,
                label=lvl.label,
                photo_cap=lvl.photo_cap,
                video_cap=lvl.video_cap,
                estimated_cost_usd_low=lvl.estimated_cost_usd_low,
                estimated_cost_usd_high=lvl.estimated_cost_usd_high,
                description=lvl.description,
                fits_today_budget=fits,
            )
        )
    recommended = next(
        (lvl.id for lvl in reversed(out_levels) if lvl.fits_today_budget),
        None,
    )
    return EffortLevelsResponse(
        levels=out_levels,
        today_total_spent_usd=spent_total,
        today_per_provider_spent_usd=spent_per_provider,
        cap_total_usd=cap_total,
        cap_per_provider_usd=cap_per_provider,
        recommended_level_id=recommended,
    )


# ---- Cost preview ------------------------------------------------------


class CostPreviewRequest(BaseModel):
    media_count: int = Field(ge=0)
    target_duration_seconds: int = Field(ge=1)
    level_id: str | None = None


class CostPreviewResponse(BaseModel):
    estimated_cost_usd_low: float
    estimated_cost_usd_high: float
    cost_by_tier_usd: dict[str, float]
    today_remaining_usd: float | None
    fits_today_budget: bool
    blocking_reason: str | None


@router.post("/cost-preview", response_model=CostPreviewResponse)
async def post_cost_preview(req: CostPreviewRequest) -> CostPreviewResponse:
    """Per-tier cost preview for a job of this size.

    Mirrors `runner._estimate_cost_per_provider` (pessimistic) but breaks
    the estimate down by tier so the UI can render it.
    """
    n = max(req.media_count, 1)
    tier_estimate = {
        "S": 0.001 * n * 3,  # ~3 Tier-S calls per asset (caption + 2 scores)
        "M": 0.005 * n,  # 1 Tier-M metadata extract per asset
        "L": 0.50,  # 1 Tier-L narrative judgment per job
        "embedding": 0.0001 * n,
    }
    estimate_total = sum(tier_estimate.values())
    # Build a low/high range: low = estimate_total, high = 1.6× as a buffer
    # for token-usage variance.
    low = estimate_total
    high = estimate_total * 1.6

    cap_total = await quota._read_total_cap()
    today = await quota.get_today_spend()
    spent_total = float(today.get("_total_", 0.0))
    remaining: float | None = None
    fits = True
    blocking: str | None = None
    if cap_total is None:
        fits = False
        blocking = "no_total_cap_configured"
    else:
        remaining = cap_total - spent_total
        if remaining < high:
            fits = False
            blocking = "insufficient_remaining_budget"

    return CostPreviewResponse(
        estimated_cost_usd_low=round(low, 4),
        estimated_cost_usd_high=round(high, 4),
        cost_by_tier_usd={k: round(v, 4) for k, v in tier_estimate.items()},
        today_remaining_usd=remaining,
        fits_today_budget=fits,
        blocking_reason=blocking,
    )


# Suppress F401 — `Any`, `HTTPException`, `status` reserved for future
# error paths but not used in M3.
_ = (Any, HTTPException, status)
