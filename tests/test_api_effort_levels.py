"""Tests for GET /api/effort-levels + POST /api/cost-preview."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from impact_crater import quota
from impact_crater.app import create_app
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---- Effort levels ----------------------------------------------------


async def test_effort_levels_returns_three_levels(client: httpx.AsyncClient) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")
    r = await client.get("/api/effort-levels")
    assert r.status_code == 200
    body = r.json()
    assert [lvl["id"] for lvl in body["levels"]] == ["L1", "L2", "L3"]
    assert all(lvl["fits_today_budget"] for lvl in body["levels"])
    assert body["recommended_level_id"] == "L3"


async def test_effort_levels_recommends_l1_under_tight_cap(
    client: httpx.AsyncClient,
) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "3.00")
    r = await client.get("/api/effort-levels")
    body = r.json()
    fits = {lvl["id"]: lvl["fits_today_budget"] for lvl in body["levels"]}
    assert fits["L1"] is True
    assert fits["L2"] is False  # high-end is $7
    assert fits["L3"] is False
    assert body["recommended_level_id"] == "L1"


async def test_effort_levels_no_cap_means_no_recommended(
    client: httpx.AsyncClient,
) -> None:
    r = await client.get("/api/effort-levels")
    body = r.json()
    assert body["cap_total_usd"] is None
    assert body["recommended_level_id"] is None
    assert all(not lvl["fits_today_budget"] for lvl in body["levels"])


async def test_effort_levels_subtracts_today_spent(
    client: httpx.AsyncClient,
) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "10.00")
    await quota.record_spend("anthropic", 5.00)
    r = await client.get("/api/effort-levels")
    body = r.json()
    # $5 already spent; L2 high = $7 → 5 + 7 = 12 > 10 → doesn't fit.
    fits = {lvl["id"]: lvl["fits_today_budget"] for lvl in body["levels"]}
    assert fits["L1"] is True
    assert fits["L2"] is False


# ---- Cost preview -----------------------------------------------------


async def test_cost_preview_under_budget(client: httpx.AsyncClient) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")
    r = await client.post(
        "/api/cost-preview",
        json={"media_count": 100, "target_duration_seconds": 60},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["fits_today_budget"] is True
    assert body["estimated_cost_usd_high"] > body["estimated_cost_usd_low"]
    assert "S" in body["cost_by_tier_usd"]
    assert "M" in body["cost_by_tier_usd"]


async def test_cost_preview_title_card_line_item(client: httpx.AsyncClient) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")
    base = (await client.post("/api/cost-preview",
            json={"media_count": 50, "target_duration_seconds": 60})).json()
    withcard = (await client.post("/api/cost-preview",
                json={"media_count": 50, "target_duration_seconds": 60, "add_title_card": True})).json()
    assert base["title_card_cost_usd"] is None
    assert withcard["title_card_cost_usd"] == 0.04
    assert "title_card" in withcard["cost_by_tier_usd"]
    assert withcard["estimated_cost_usd_high"] > base["estimated_cost_usd_high"]


async def test_cost_preview_blocked_when_no_cap(
    client: httpx.AsyncClient,
) -> None:
    r = await client.post(
        "/api/cost-preview",
        json={"media_count": 100, "target_duration_seconds": 60},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["fits_today_budget"] is False
    assert body["blocking_reason"] == "no_total_cap_configured"


async def test_cost_preview_blocked_when_remaining_too_small(
    client: httpx.AsyncClient,
) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "1.00")
    r = await client.post(
        "/api/cost-preview",
        json={"media_count": 1000, "target_duration_seconds": 120},
    )
    body = r.json()
    assert body["fits_today_budget"] is False
    assert body["blocking_reason"] == "insufficient_remaining_budget"
