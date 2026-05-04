"""Tests for the /api/setup/* endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from impact_crater.app import create_app
from impact_crater.storage import settings as settings_store
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


VALID_PAYLOAD = {
    "anthropic_api_key": "sk-ant-test-001",
    "google_api_key": "AIza-test-002",
    "spend_cap_total_usd": 50.0,
    "spend_cap_anthropic_usd": 30.0,
    "spend_cap_google_usd": 20.0,
}


async def test_status_returns_false_before_completion(client: httpx.AsyncClient) -> None:
    await run_pending_migrations()
    r = await client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json() == {"setup_complete": False}


async def test_test_key_accepts_non_empty_key(client: httpx.AsyncClient) -> None:
    await run_pending_migrations()
    r = await client.post(
        "/api/setup/test-key",
        json={"provider": "anthropic", "key": "sk-ant-anything"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "Anthropic" in body["message"]


async def test_test_key_rejects_empty_key(client: httpx.AsyncClient) -> None:
    # Pydantic catches empty strings via min_length, returning 422.
    r = await client.post(
        "/api/setup/test-key",
        json={"provider": "google", "key": ""},
    )
    assert r.status_code == 422


async def test_test_key_rejects_unknown_provider(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/setup/test-key",
        json={"provider": "openai", "key": "sk-..."},
    )
    assert r.status_code == 422


async def test_complete_flow_persists_and_encrypts(client: httpx.AsyncClient) -> None:
    await run_pending_migrations()

    r = await client.post("/api/setup/complete", json=VALID_PAYLOAD)
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # status now reports complete
    r = await client.get("/api/setup/status")
    assert r.json() == {"setup_complete": True}

    # API keys were persisted + encrypted
    decrypted_a = await settings_store.get_value(settings_store.KEY_ANTHROPIC_API_KEY)
    decrypted_g = await settings_store.get_value(settings_store.KEY_GOOGLE_API_KEY)
    assert decrypted_a == VALID_PAYLOAD["anthropic_api_key"]
    assert decrypted_g == VALID_PAYLOAD["google_api_key"]

    async with connection() as db:
        cursor = await db.execute(
            "SELECT value, encrypted FROM settings WHERE key = ?",
            (settings_store.KEY_ANTHROPIC_API_KEY,),
        )
        row = await cursor.fetchone()
    assert row["encrypted"] == 1
    assert row["value"] != VALID_PAYLOAD["anthropic_api_key"]

    # Spend caps stored as numeric strings
    assert await settings_store.get_value(settings_store.KEY_TOTAL_CAP_USD) == "50.0"
    assert await settings_store.get_value(settings_store.KEY_ANTHROPIC_CAP_USD) == "30.0"
    assert await settings_store.get_value(settings_store.KEY_GOOGLE_CAP_USD) == "20.0"


async def test_complete_rejects_per_provider_cap_above_total(
    client: httpx.AsyncClient,
) -> None:
    await run_pending_migrations()
    bad = {**VALID_PAYLOAD, "spend_cap_anthropic_usd": 999.0}
    r = await client.post("/api/setup/complete", json=bad)
    assert r.status_code == 422


async def test_complete_rejects_total_cap_below_minimum(
    client: httpx.AsyncClient,
) -> None:
    await run_pending_migrations()
    bad = {**VALID_PAYLOAD, "spend_cap_total_usd": 0.5}
    r = await client.post("/api/setup/complete", json=bad)
    assert r.status_code == 422


async def test_complete_optional_per_provider_caps_can_be_omitted(
    client: httpx.AsyncClient,
) -> None:
    await run_pending_migrations()
    minimal = {
        "anthropic_api_key": "sk-ant-min",
        "google_api_key": "AIza-min",
        "spend_cap_total_usd": 25.0,
    }
    r = await client.post("/api/setup/complete", json=minimal)
    assert r.status_code == 200
    assert await settings_store.get_value(settings_store.KEY_ANTHROPIC_CAP_USD) == ""
    assert await settings_store.get_value(settings_store.KEY_GOOGLE_CAP_USD) == ""


async def test_complete_is_409_if_already_setup(client: httpx.AsyncClient) -> None:
    await run_pending_migrations()
    r1 = await client.post("/api/setup/complete", json=VALID_PAYLOAD)
    assert r1.status_code == 200
    r2 = await client.post("/api/setup/complete", json=VALID_PAYLOAD)
    assert r2.status_code == 409
