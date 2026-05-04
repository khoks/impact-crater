"""First-time-setup wizard API.

Per ADR-0015 the first-time-setup wizard is the *only* path through
which the user lands API keys + spend caps. This module backs the
6-step React form (frontend/src/routes/Setup.tsx) and the underlying
storage in the SQLite settings table (Fernet-encrypted for keys).

Endpoints:
  GET  /api/setup/status          → {setup_complete: bool}
  POST /api/setup/test-key        → {success: bool, message: str}
  POST /api/setup/complete        → {ok: true} after persisting all values
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from impact_crater.storage import settings as settings_store

router = APIRouter()


# -- Schemas -------------------------------------------------------------

Provider = Literal["anthropic", "google"]


class StatusResponse(BaseModel):
    setup_complete: bool


class TestKeyRequest(BaseModel):
    provider: Provider
    key: str = Field(min_length=1, max_length=512)


class TestKeyResponse(BaseModel):
    success: bool
    message: str


class CompleteRequest(BaseModel):
    anthropic_api_key: str = Field(min_length=1, max_length=512)
    google_api_key: str = Field(min_length=1, max_length=512)
    spend_cap_total_usd: float = Field(ge=1.0, le=100_000.0)
    spend_cap_anthropic_usd: float | None = Field(default=None, ge=0.0, le=100_000.0)
    spend_cap_google_usd: float | None = Field(default=None, ge=0.0, le=100_000.0)
    impact_crater_home_override: str | None = None

    @field_validator("spend_cap_anthropic_usd", "spend_cap_google_usd")
    @classmethod
    def _per_provider_cap_within_total(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        # Pydantic 2 calls validators in declaration order; total is required
        # and lands in `info.data` before per-provider caps.
        total = info.data.get("spend_cap_total_usd")
        if v is not None and total is not None and v > total:
            raise ValueError(
                f"per-provider cap (${v}) cannot exceed total cap (${total})"
            )
        return v


class CompleteResponse(BaseModel):
    ok: bool


# -- Endpoints -----------------------------------------------------------


@router.get("/status", response_model=StatusResponse)
async def status_endpoint() -> StatusResponse:
    return StatusResponse(setup_complete=await settings_store.is_setup_complete())


@router.post("/test-key", response_model=TestKeyResponse)
async def test_key(req: TestKeyRequest) -> TestKeyResponse:
    """Stub key-test at M0.

    A real provider ping (small models.list call against the Anthropic /
    Google APIs) lands in M1 (E-2.2 headless curation through Stage 5)
    when the LLM client implementations land. M0 only validates that the
    key string is non-empty + provider is recognised so the wizard can
    show a green checkmark.
    """
    if not req.key.strip():
        return TestKeyResponse(success=False, message="API key is empty.")
    return TestKeyResponse(
        success=True,
        message=(
            f"{req.provider.title()} key accepted. Real provider ping lands "
            "in M1 (E-2.2)."
        ),
    )


@router.post("/complete", response_model=CompleteResponse)
async def complete(req: CompleteRequest) -> CompleteResponse:
    if await settings_store.is_setup_complete():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup is already complete. Edit settings via the dashboard.",
        )

    # Encrypt the API keys at rest per ADR-0013.
    await settings_store.set_value(
        settings_store.KEY_ANTHROPIC_API_KEY,
        req.anthropic_api_key,
        encrypted=True,
    )
    await settings_store.set_value(
        settings_store.KEY_GOOGLE_API_KEY,
        req.google_api_key,
        encrypted=True,
    )

    # Spend caps stored as plain numeric strings.
    await settings_store.set_value(
        settings_store.KEY_TOTAL_CAP_USD,
        str(req.spend_cap_total_usd),
    )
    await settings_store.set_value(
        settings_store.KEY_ANTHROPIC_CAP_USD,
        "" if req.spend_cap_anthropic_usd is None else str(req.spend_cap_anthropic_usd),
    )
    await settings_store.set_value(
        settings_store.KEY_GOOGLE_CAP_USD,
        "" if req.spend_cap_google_usd is None else str(req.spend_cap_google_usd),
    )

    # IMPACT_CRATER_HOME override is read at process start via the env var,
    # so persisting it here is informational only — the user has to set the
    # env var themselves on next launch. Note this on the wizard's Step 5.
    if req.impact_crater_home_override:
        await settings_store.set_value(
            "impact_crater_home_override_preference",
            req.impact_crater_home_override,
        )

    await settings_store.mark_setup_complete()
    return CompleteResponse(ok=True)
