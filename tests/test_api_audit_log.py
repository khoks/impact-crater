"""Tests for GET /api/audit — the cross-project publish log (S-3.3.9)."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from impact_crater import api_auth, audit
from impact_crater.app import create_app
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        yield ac


async def _seed(project_id: str, name: str, snapshots: dict[str, str | None]) -> None:
    async with connection() as db:
        await db.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (project_id, name))
        for snapshot_id, render_path in snapshots.items():
            await db.execute(
                "INSERT INTO snapshots (id, project_id, render_path, render_status) "
                "VALUES (?, ?, ?, 'success')",
                (snapshot_id, project_id, render_path),
            )
        await db.commit()


async def _publish(
    project_id: str, snapshot_id: str, platform: str, at: str, render_hash: str = ""
) -> None:
    await audit.write(
        audit.AuditEntry(
            project_id=project_id,
            snapshot_id=snapshot_id,
            platform=platform,
            external_id="ext",
            external_url=f"https://example.com/{snapshot_id}",
            user_approval_token=f"tok-{at}",
            render_content_hash=render_hash,
            visibility="private",
            timestamp=at,
        )
    )


async def test_lists_every_project_newest_first_and_pages(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    await _seed("p-a", "Zion", {"s-a": None})
    await _seed("p-b", "Vegas", {"s-b": None})
    await _publish("p-a", "s-a", "youtube (dry-run)", "2026-11-01T10:00:00+00:00")
    await _publish("p-b", "s-b", "youtube", "2026-11-03T10:00:00+00:00")
    await _publish("p-a", "s-a", "facebook (dry-run)", "2026-11-02T10:00:00+00:00")

    page = (await client.get("/api/audit", params={"limit": 2})).json()
    assert page["total"] == 3
    assert [(r["project_name"], r["platform"], r["dry_run"]) for r in page["items"]] == [
        ("Vegas", "youtube", False),
        ("Zion", "facebook", True),
    ]
    assert page["items"][0]["visibility"] == "private"
    assert page["items"][0]["approval_token"] == "tok-2026-11-03T10:00:00+00:00"

    rest = (await client.get("/api/audit", params={"limit": 2, "offset": 2})).json()
    assert [r["published_at"] for r in rest["items"]] == ["2026-11-01T10:00:00+00:00"]
    assert rest["offset"] == 2


async def test_render_check_states(client: httpx.AsyncClient, tmp_path: Path) -> None:
    same = tmp_path / "same.mp4"
    same.write_bytes(b"approved video")
    edited = tmp_path / "edited.mp4"
    edited.write_bytes(b"approved video")
    approved = hashlib.sha256(b"approved video").hexdigest()
    edited.write_bytes(b"re-rendered later")

    await _seed(
        "p-c",
        "Checks",
        {
            "s-match": str(same),
            "s-changed": str(edited),
            "s-missing": str(tmp_path / "gone.mp4"),
            "s-old": str(same),
        },
    )
    await _publish("p-c", "s-match", "youtube", "2026-11-04T10:00:00+00:00", approved)
    await _publish("p-c", "s-changed", "youtube", "2026-11-03T10:00:00+00:00", approved)
    await _publish("p-c", "s-missing", "youtube", "2026-11-02T10:00:00+00:00", approved)
    await _publish("p-c", "s-old", "youtube (dry-run)", "2026-11-01T10:00:00+00:00")

    items = (await client.get("/api/audit")).json()["items"]
    assert {r["snapshot_id"]: r["render_check"] for r in items} == {
        "s-match": "match",
        "s-changed": "changed",
        "s-missing": "missing",
        "s-old": "unrecorded",
    }


async def test_rejects_bad_paging(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/audit", params={"limit": 0})).status_code == 422
    assert (await client.get("/api/audit", params={"offset": -1})).status_code == 422


async def test_needs_the_api_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/audit", headers={"Authorization": ""})
    assert r.status_code == 401
