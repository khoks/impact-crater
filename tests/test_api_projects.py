"""Tests for GET /api/projects — the dashboard's persistent project list (S-2.9.2)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from impact_crater.app import create_app
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _seed_project(
    project_id: str, *, name: str, brief: str | None, created_at: str
) -> None:
    async with connection() as db:
        await db.execute(
            "INSERT INTO projects (id, name, brief, created_at) VALUES (?, ?, ?, ?)",
            (project_id, name, brief, created_at),
        )
        await db.commit()


async def _seed_snapshot(
    snapshot_id: str,
    project_id: str,
    *,
    render_status: str,
    render_path: str | None,
    created_at: str,
) -> None:
    async with connection() as db:
        await db.execute(
            "INSERT INTO snapshots (id, project_id, render_status, render_path, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, project_id, render_status, render_path, created_at),
        )
        await db.commit()


async def test_empty_db_returns_empty_list(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == []


async def test_projects_listed_newest_first_with_snapshots(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    render = tmp_path / "render.mp4"
    render.write_bytes(b"\x00fakevideo")

    await _seed_project("proj-old", name="Zion trip", brief="canyon hike", created_at="2026-06-01 10:00:00")
    await _seed_project("proj-new", name="proj-new", brief=None, created_at="2026-06-10 10:00:00")
    await _seed_snapshot(
        "snap-ok", "proj-old",
        render_status="success", render_path=str(render), created_at="2026-06-01 11:00:00",
    )
    await _seed_snapshot(
        "snap-gone", "proj-old",
        render_status="success", render_path=str(tmp_path / "deleted.mp4"), created_at="2026-06-01 12:00:00",
    )
    await _seed_snapshot(
        "snap-pending", "proj-new",
        render_status="pending", render_path=None, created_at="2026-06-10 11:00:00",
    )

    r = await client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert [p["id"] for p in body] == ["proj-new", "proj-old"]  # newest first

    new_proj = body[0]
    assert new_proj["name"] == "proj-new"
    assert new_proj["brief"] == ""  # null normalizes to empty string
    assert [s["id"] for s in new_proj["snapshots"]] == ["snap-pending"]
    assert new_proj["snapshots"][0]["has_render"] is False

    old_proj = body[1]
    assert old_proj["brief"] == "canyon hike"
    # Snapshots newest first; missing file on disk → has_render False even
    # though render_status says success.
    assert [s["id"] for s in old_proj["snapshots"]] == ["snap-gone", "snap-ok"]
    by_id = {s["id"]: s for s in old_proj["snapshots"]}
    assert by_id["snap-ok"]["has_render"] is True
    assert by_id["snap-gone"]["has_render"] is False
