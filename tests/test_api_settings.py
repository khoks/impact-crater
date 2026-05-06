"""Tests for /api/settings/snapshot + /api/settings/update."""

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


async def test_settings_snapshot_empty_state(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/settings/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["has_anthropic_key"] is False
    assert body["has_google_key"] is False
    assert body["spend_cap_total_usd"] is None
    assert body["today_total_spent_usd"] == 0.0


async def test_settings_snapshot_after_setup(client: httpx.AsyncClient) -> None:
    await settings_store.set_value(
        settings_store.KEY_ANTHROPIC_API_KEY, "sk-ant-test", encrypted=True
    )
    await settings_store.set_value(
        settings_store.KEY_GOOGLE_API_KEY, "AIza-test", encrypted=True
    )
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "50.00")
    await settings_store.set_value(settings_store.KEY_ANTHROPIC_CAP_USD, "30.00")
    await quota.record_spend("anthropic", 1.50)

    r = await client.get("/api/settings/snapshot")
    body = r.json()
    assert body["has_anthropic_key"] is True
    assert body["has_google_key"] is True
    assert body["spend_cap_total_usd"] == 50.0
    assert body["spend_cap_anthropic_usd"] == 30.0
    assert body["spend_cap_google_usd"] is None
    assert body["today_total_spent_usd"] == 1.5
    # Plaintext keys are NEVER returned.
    assert "anthropic_api_key" not in body
    assert "google_api_key" not in body


async def test_settings_update_caps_only(client: httpx.AsyncClient) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "10.00")
    r = await client.post(
        "/api/settings/update", json={"spend_cap_total_usd": 75.0}
    )
    assert r.status_code == 200
    snap = (await client.get("/api/settings/snapshot")).json()
    assert snap["spend_cap_total_usd"] == 75.0


async def test_settings_update_rotates_anthropic_key(
    client: httpx.AsyncClient,
) -> None:
    await settings_store.set_value(
        settings_store.KEY_ANTHROPIC_API_KEY, "sk-ant-old", encrypted=True
    )
    r = await client.post(
        "/api/settings/update", json={"anthropic_api_key": "sk-ant-new"}
    )
    assert r.status_code == 200
    new = await settings_store.get_value(settings_store.KEY_ANTHROPIC_API_KEY)
    assert new == "sk-ant-new"


async def test_settings_update_rejects_out_of_range_cap(
    client: httpx.AsyncClient,
) -> None:
    r = await client.post(
        "/api/settings/update", json={"spend_cap_total_usd": 0.50}
    )
    assert r.status_code == 422
