"""Tests for the workplan tracker API (A-024)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from impact_crater.app import create_app
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    # Point the workplan parser at a synthetic project/ tree.
    proj = tmp_path / "project"
    (proj / "initiatives").mkdir(parents=True)
    (proj / "epics").mkdir()
    (proj / "stories").mkdir()
    (proj / "tasks").mkdir()
    (proj / "initiatives" / "I-2-mvp.md").write_text(
        "---\nid: I-2\ntitle: MVP\ntype: initiative\nstatus: in-progress\n"
        "priority: P0\nphase: mvp\ntags: [mvp]\n---\n\n## North-star\n",
        encoding="utf-8",
    )
    (proj / "epics" / "E-2.9-profile.md").write_text(
        "---\nid: E-2.9\ntitle: Profile epic\ntype: epic\nstatus: in-progress\n"
        "priority: P1\nparent: I-2\nphase: mvp\n---\n",
        encoding="utf-8",
    )
    (proj / "stories" / "S-2.9.8-feedback.md").write_text(
        "---\nid: S-2.9.8\ntitle: Feedback loop\ntype: story\nstatus: done\n"
        "priority: P1\nparent: E-2.9\nphase: mvp\n---\n",
        encoding="utf-8",
    )
    (proj / "stories" / "S-2.9.7-crowd.md").write_text(
        "---\nid: S-2.9.7\ntitle: Crowd removal\ntype: story\nstatus: ready\n"
        "priority: P3\nparent: E-2.9\nphase: v2\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("IMPACT_CRATER_PROJECT_DIR", str(proj))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_workplan_parses_hierarchy(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/workplan")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    by_id = {it["id"]: it for it in body["items"]}
    assert set(by_id) == {"I-2", "E-2.9", "S-2.9.8", "S-2.9.7"}
    assert by_id["I-2"]["type"] == "initiative"
    assert by_id["I-2"]["parent"] is None
    assert by_id["E-2.9"]["parent"] == "I-2"
    assert by_id["S-2.9.8"]["status"] == "done"
    assert by_id["S-2.9.7"]["phase"] == "v2"
    # Rollups.
    assert body["counts_by_status"]["done"] == 1
    assert body["counts_by_status"]["in-progress"] == 2
    assert body["counts_by_phase"]["mvp"] == 3
    assert body["counts_by_phase"]["v2"] == 1


async def test_workplan_priority_override(client: httpx.AsyncClient) -> None:
    # S-2.9.7 is P3 in markdown; override to P0.
    r = await client.patch("/api/workplan/S-2.9.7", json={"priority": "P0", "note": "do this now"})
    assert r.status_code == 200

    body = (await client.get("/api/workplan")).json()
    s = next(it for it in body["items"] if it["id"] == "S-2.9.7")
    assert s["priority"] == "P0"  # effective
    assert s["markdown_priority"] == "P3"  # canonical untouched
    assert s["priority_overridden"] is True
    assert s["override_note"] == "do this now"

    # Surfaced for Claude pickup.
    overrides = (await client.get("/api/workplan/overrides")).json()
    assert any(o["item_id"] == "S-2.9.7" and o["priority"] == "P0" for o in overrides)


async def test_workplan_empty_when_no_project_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run_pending_migrations()
    monkeypatch.setenv("IMPACT_CRATER_PROJECT_DIR", str(tmp_path / "does-not-exist"))
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        body = (await ac.get("/api/workplan")).json()
    assert body["available"] is False
    assert body["items"] == []
