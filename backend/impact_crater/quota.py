"""Dual-cap (total + per-provider) daily spend quota per ADR-0015 §"Dual-cap quota model".

State lives in the SQLite `quota_state` table (one row per (date, provider);
the synthetic "_total_" provider tracks the all-providers aggregate).

The pre-job and per-stage check call `check_quota(estimated_cost_per_provider)`;
post-call, every successful LLM dispatch records into `record_spend()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from impact_crater.storage import settings as settings_store
from impact_crater.storage.db import connection

_TOTAL_PROVIDER = "_total_"


@dataclass(frozen=True)
class QuotaCheck:
    """Outcome of `check_quota`."""

    allowed: bool
    reason: str = ""
    today_total_spent_usd: float = 0.0
    today_per_provider_spent_usd: dict[str, float] | None = None
    cap_total_usd: float | None = None
    cap_per_provider_usd: dict[str, float] | None = None


# ---- Public API --------------------------------------------------------


async def check_quota(
    estimated_cost_per_provider: dict[str, float],
    *,
    today: date | None = None,
) -> QuotaCheck:
    """Decide whether a job projected to spend `estimated_cost_per_provider`
    can start without breaching either cap.
    """
    today = today or date.today()
    iso = today.isoformat()

    cap_total = await _read_total_cap()
    if cap_total is None:
        # No cap configured yet — fail-safe to disallow rather than risk
        # runaway spend. The first-time-setup wizard is supposed to make
        # the user set this; if it didn't, the user knows immediately.
        return QuotaCheck(
            allowed=False,
            reason="no_total_cap_configured",
        )

    cap_per_provider = await _read_per_provider_caps()

    spent_total = await _read_spent(_TOTAL_PROVIDER, iso)
    spent_per_provider: dict[str, float] = {}
    for provider in set(estimated_cost_per_provider) | set(cap_per_provider):
        spent_per_provider[provider] = await _read_spent(provider, iso)

    estimated_total = sum(estimated_cost_per_provider.values())

    if spent_total + estimated_total > cap_total:
        return QuotaCheck(
            allowed=False,
            reason="total_cap_would_be_exceeded",
            today_total_spent_usd=spent_total,
            today_per_provider_spent_usd=spent_per_provider,
            cap_total_usd=cap_total,
            cap_per_provider_usd=cap_per_provider,
        )

    for provider, est in estimated_cost_per_provider.items():
        cap = cap_per_provider.get(provider)
        if cap is None:
            continue
        if spent_per_provider.get(provider, 0.0) + est > cap:
            return QuotaCheck(
                allowed=False,
                reason=f"{provider}_cap_would_be_exceeded",
                today_total_spent_usd=spent_total,
                today_per_provider_spent_usd=spent_per_provider,
                cap_total_usd=cap_total,
                cap_per_provider_usd=cap_per_provider,
            )

    return QuotaCheck(
        allowed=True,
        today_total_spent_usd=spent_total,
        today_per_provider_spent_usd=spent_per_provider,
        cap_total_usd=cap_total,
        cap_per_provider_usd=cap_per_provider,
    )


async def record_spend(
    provider: str,
    amount_usd: float,
    *,
    today: date | None = None,
) -> None:
    """Add `amount_usd` to today's spent total for `provider`, plus the
    `_total_` aggregate row. Idempotent against double-counting only when
    the caller dedupes upstream (per ADR-0015 — every LLMCallEvent emit
    triggers exactly one record_spend).
    """
    if amount_usd <= 0:
        return
    today = today or date.today()
    iso = today.isoformat()
    await _bump_spent(provider, iso, amount_usd)
    await _bump_spent(_TOTAL_PROVIDER, iso, amount_usd)


async def get_today_spend(
    *,
    today: date | None = None,
) -> dict[str, float]:
    """Return a snapshot of today's per-provider spend (incl. `_total_`)."""
    today = today or date.today()
    iso = today.isoformat()
    out: dict[str, float] = {}
    async with connection() as db:
        cursor = await db.execute(
            "SELECT provider, spent_usd FROM quota_state WHERE date = ?",
            (iso,),
        )
        rows = await cursor.fetchall()
    for row in rows:
        out[row["provider"]] = float(row["spent_usd"])
    return out


# ---- Internal ---------------------------------------------------------


async def _read_total_cap() -> float | None:
    raw = await settings_store.get_value(settings_store.KEY_TOTAL_CAP_USD)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


async def _read_per_provider_caps() -> dict[str, float]:
    out: dict[str, float] = {}
    for key, provider in [
        (settings_store.KEY_ANTHROPIC_CAP_USD, "anthropic"),
        (settings_store.KEY_GOOGLE_CAP_USD, "google"),
    ]:
        raw = await settings_store.get_value(key)
        if raw is None or raw == "":
            continue
        try:
            out[provider] = float(raw)
        except ValueError:
            continue
    return out


async def _read_spent(provider: str, iso_date: str) -> float:
    async with connection() as db:
        cursor = await db.execute(
            "SELECT spent_usd FROM quota_state WHERE date = ? AND provider = ?",
            (iso_date, provider),
        )
        row = await cursor.fetchone()
    return float(row["spent_usd"]) if row else 0.0


async def _bump_spent(provider: str, iso_date: str, delta: float) -> None:
    async with connection() as db:
        await db.execute(
            """
            INSERT INTO quota_state (date, provider, spent_usd, last_updated)
            VALUES (?, ?, ?, CAST(strftime('%s','now') AS INTEGER))
            ON CONFLICT(date, provider) DO UPDATE SET
                spent_usd = spent_usd + excluded.spent_usd,
                last_updated = excluded.last_updated
            """,
            (iso_date, provider, delta),
        )
        await db.commit()
