"""Settings panel API per S-2.4.5.

Post-setup-wizard the user edits keys + caps via these endpoints.
Mirrors the wizard's data model but never returns plaintext API keys
on read — the snapshot only carries booleans + cap floats.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from impact_crater import quota
from impact_crater.storage import settings as settings_store

router = APIRouter()


class SettingsSnapshotResponse(BaseModel):
    has_anthropic_key: bool
    has_google_key: bool
    spend_cap_total_usd: float | None
    spend_cap_anthropic_usd: float | None
    spend_cap_google_usd: float | None
    today_total_spent_usd: float
    today_per_provider_spent_usd: dict[str, float]


class SettingsUpdateRequest(BaseModel):
    """Optional fields — empty / null = leave unchanged."""

    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    spend_cap_total_usd: float | None = Field(default=None, ge=1.0, le=100_000.0)
    spend_cap_anthropic_usd: float | None = Field(default=None, ge=0.0, le=100_000.0)
    spend_cap_google_usd: float | None = Field(default=None, ge=0.0, le=100_000.0)


@router.get("/snapshot", response_model=SettingsSnapshotResponse)
async def settings_snapshot() -> SettingsSnapshotResponse:
    anthropic = await settings_store.get_value(settings_store.KEY_ANTHROPIC_API_KEY)
    google = await settings_store.get_value(settings_store.KEY_GOOGLE_API_KEY)
    total_raw = await settings_store.get_value(settings_store.KEY_TOTAL_CAP_USD)
    anthropic_cap_raw = await settings_store.get_value(settings_store.KEY_ANTHROPIC_CAP_USD)
    google_cap_raw = await settings_store.get_value(settings_store.KEY_GOOGLE_CAP_USD)

    today = await quota.get_today_spend()
    spent_total = float(today.get("_total_", 0.0))
    spent_per_provider = {k: v for k, v in today.items() if k != "_total_"}

    return SettingsSnapshotResponse(
        has_anthropic_key=bool(anthropic),
        has_google_key=bool(google),
        spend_cap_total_usd=_parse_float(total_raw),
        spend_cap_anthropic_usd=_parse_float(anthropic_cap_raw),
        spend_cap_google_usd=_parse_float(google_cap_raw),
        today_total_spent_usd=spent_total,
        today_per_provider_spent_usd=spent_per_provider,
    )


@router.post("/update")
async def settings_update(req: SettingsUpdateRequest) -> dict[str, bool]:
    """Apply partial updates. Null fields are ignored."""
    if req.anthropic_api_key:
        await settings_store.set_value(
            settings_store.KEY_ANTHROPIC_API_KEY, req.anthropic_api_key, encrypted=True
        )
    if req.google_api_key:
        await settings_store.set_value(
            settings_store.KEY_GOOGLE_API_KEY, req.google_api_key, encrypted=True
        )
    if req.spend_cap_total_usd is not None:
        await settings_store.set_value(
            settings_store.KEY_TOTAL_CAP_USD, str(req.spend_cap_total_usd)
        )
    if req.spend_cap_anthropic_usd is not None:
        await settings_store.set_value(
            settings_store.KEY_ANTHROPIC_CAP_USD, str(req.spend_cap_anthropic_usd)
        )
    if req.spend_cap_google_usd is not None:
        await settings_store.set_value(
            settings_store.KEY_GOOGLE_CAP_USD, str(req.spend_cap_google_usd)
        )
    return {"ok": True}


def _parse_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None
