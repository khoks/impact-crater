"""Tests for the publish API."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from impact_crater.api import publish
from impact_crater.app import create_app
from impact_crater.connectors import ConnectorUploadResult
from impact_crater.connectors.youtube import YouTubeConnector, store_credentials
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


class FakeTransport:
    def __init__(self, *, fail: bool = False, fail_code: int = 500) -> None:
        self.fail = fail
        self.fail_code = fail_code

    def refresh(self, creds):
        return creds

    async def upload(self, *, render_path, metadata, credentials, on_progress):
        if self.fail:
            from impact_crater.connectors import ConnectorError

            raise ConnectorError("simulated", status_code=self.fail_code)
        privacy = metadata.get("status", {}).get("privacyStatus", "public")
        return ConnectorUploadResult(
            external_id="vid-test",
            external_url="https://youtube.com/watch?v=vid-test",
            visibility=privacy,
            response_code=200,
        )


@pytest.fixture
async def setup_publish(tmp_path: Path):
    await run_pending_migrations()
    project_id = "p-pub"
    snapshot_id = "snap-pub-1"
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    render_path = tmp_path / "render.mp4"
    render_path.write_bytes(b"\x00" * 4096)
    async with connection() as db:
        await db.execute(
            "INSERT OR IGNORE INTO projects (id, name) VALUES (?, ?)",
            (project_id, project_id),
        )
        await db.execute(
            """
            INSERT INTO snapshots (id, project_id, plan_path, render_path, render_status)
            VALUES (?, ?, ?, ?, 'success')
            """,
            (snapshot_id, project_id, str(plan_path), str(render_path)),
        )
        await db.commit()
    await store_credentials(
        {
            "user_handle": "test-user",
            "access_token": "tok",
            "refresh_token": "rfr",
            "expires_at": int(time.time()) + 3600,
            "scopes_granted": ["youtube.upload"],
        }
    )
    return (project_id, snapshot_id, render_path)


@pytest.fixture
async def client_with_setup(setup_publish) -> AsyncIterator[tuple[httpx.AsyncClient, str, str]]:
    project_id, snapshot_id, _ = setup_publish
    publish.set_connector_factory(lambda: YouTubeConnector(transport=FakeTransport()))
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield (ac, project_id, snapshot_id)
    publish.set_connector_factory(lambda: YouTubeConnector())


# ---- Tests -------------------------------------------------------------


async def test_publish_returns_url_and_writes_audit(client_with_setup) -> None:
    client, project_id, snapshot_id = client_with_setup
    r = await client.post(
        f"/api/snapshots/{snapshot_id}/publish",
        json={
            "title": "Test publish",
            "description": "from the test suite",
            "tags": ["test"],
            "visibility": "unlisted",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["external_id"] == "vid-test"
    assert body["external_url"].startswith("https://youtube.com/")
    assert body["visibility"] == "unlisted"
    assert len(body["audit_token"]) > 8

    # Audit row should be present.
    audit_resp = await client.get(f"/api/projects/{project_id}/audit")
    rows = audit_resp.json()
    assert len(rows) == 1
    assert rows[0]["external_id"] == "vid-test"
    assert rows[0]["user_approval_token"] == body["audit_token"]


async def test_publish_404_for_unknown_snapshot(client_with_setup) -> None:
    client, _, _ = client_with_setup
    r = await client.post(
        "/api/snapshots/nope/publish",
        json={"title": "x"},
    )
    assert r.status_code == 404


async def test_publish_400_when_title_empty(client_with_setup) -> None:
    client, _, snapshot_id = client_with_setup
    r = await client.post(
        f"/api/snapshots/{snapshot_id}/publish",
        json={"title": ""},
    )
    # Pydantic min_length=1 → 422.
    assert r.status_code == 422


async def test_publish_500_path_when_connector_errors(setup_publish, monkeypatch) -> None:
    project_id, snapshot_id, _ = setup_publish
    publish.set_connector_factory(
        lambda: YouTubeConnector(transport=FakeTransport(fail=True))
    )
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            f"/api/snapshots/{snapshot_id}/publish",
            json={"title": "x"},
        )
    publish.set_connector_factory(lambda: YouTubeConnector())
    assert r.status_code == 502
    assert r.json()["detail"]["reason"] == "connector"


async def test_youtube_status_returns_connected_after_setup(client_with_setup) -> None:
    client, _, _ = client_with_setup
    r = await client.get("/api/connectors/youtube/status")
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is True
    assert body["user_handle"] == "test-user"


async def test_youtube_disconnect_clears_credentials(client_with_setup) -> None:
    client, _, _ = client_with_setup
    r = await client.post("/api/connectors/youtube/disconnect")
    assert r.status_code == 200
    status_resp = await client.get("/api/connectors/youtube/status")
    assert status_resp.json()["connected"] is False
