"""Tests for POST /api/snapshots/{id}/refine."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from impact_crater import paths
from impact_crater.app import create_app
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.pipeline import runner
from impact_crater.pipeline.stage6_plan import RenderClip, RenderPlan
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def setup_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Persist a fake snapshot + plan.json + DB row for the refine endpoint."""
    await run_pending_migrations()
    project_id = "p-refine"
    snapshot_id = "snap-refine-1"
    snap_dir = paths.projects_dir() / project_id / "snapshots" / snapshot_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    plan = RenderPlan(
        project_id=project_id,
        snapshot_id=snapshot_id,
        target_duration_ms=10_000,
        clips=[
            RenderClip(
                candidate_ref="hash-a",
                kind="photo",
                source_path="/tmp/a.jpg",
                intended_duration_ms=5000,
                aspect_ratio_action="as_is",
                role="opener",
            ),
            RenderClip(
                candidate_ref="hash-b#0",
                kind="video_scene",
                source_path="/tmp/b.mp4",
                start_seconds=0.0,
                end_seconds=5.0,
                intended_duration_ms=5000,
                aspect_ratio_action="as_is",
                role="closer",
            ),
        ],
        arc_reasoning="warm to cool",
        arc_confidence=0.7,
    )
    plan_path = snap_dir / "plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    async with connection() as db:
        await db.execute(
            "INSERT OR IGNORE INTO projects (id, name) VALUES (?, ?)",
            (project_id, project_id),
        )
        await db.execute(
            """
            INSERT INTO snapshots
                (id, project_id, plan_path, render_status)
            VALUES (?, ?, ?, 'success')
            """,
            (snapshot_id, project_id, str(plan_path)),
        )
        await db.commit()
    return (project_id, snapshot_id, snap_dir)


def _mock_router_for_refine(strategy: str, **payload_extra) -> object:
    router = AsyncMock()
    router.set_progress_sink = lambda sink: None
    router.set_telemetry_context = lambda **_: None
    payload = {
        "strategy": strategy,
        "rationale": "test rationale",
        **payload_extra,
    }
    router.parse_user_brief = AsyncMock(return_value=payload)
    router.judge_narrative_arc = AsyncMock(
        return_value=ArcJudgment(
            selected_items=[
                SelectedItem(
                    candidate_ref="hash-a",
                    placement_position=0,
                    intended_duration_ms=5000,
                    role="opener",
                ),
            ],
            arc_reasoning="refined arc",
            confidence=0.8,
        )
    )
    return router


@pytest.fixture
async def client_with_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    setup_snapshot,
) -> AsyncIterator[tuple[httpx.AsyncClient, str]]:
    project_id, snapshot_id, snap_dir = setup_snapshot

    fake_router = _mock_router_for_refine(
        "partial_fix_via_plan_edit",
        brief_addendum="Add 30% more landscape.",
    )

    async def fake_build() -> object:
        return fake_router

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield (ac, snapshot_id)


# ---- Tests -------------------------------------------------------------


async def test_refine_endpoint_returns_strategy_and_new_arc(
    client_with_snapshot,
) -> None:
    client, snapshot_id = client_with_snapshot
    r = await client.post(
        f"/api/snapshots/{snapshot_id}/refine",
        json={"refinement_message": "more landscape, less faces"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"] == "partial_fix_via_plan_edit"
    assert body["new_arc_judgment"] is not None
    assert body["new_arc_judgment"]["confidence"] == 0.8
    assert body["turns_used"] == 2


async def test_refine_endpoint_explain_strategy(
    monkeypatch: pytest.MonkeyPatch,
    setup_snapshot,
) -> None:
    project_id, snapshot_id, snap_dir = setup_snapshot
    fake_router = _mock_router_for_refine(
        "explain_why_not_possible",
        explanation="No landscape in candidate set.",
    )

    async def fake_build() -> object:
        return fake_router

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            f"/api/snapshots/{snapshot_id}/refine",
            json={"refinement_message": "more landscape"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"] == "explain_why_not_possible"
    assert body["new_arc_judgment"] is None
    assert "No landscape" in body["explanation"]


async def test_refine_endpoint_persists_refinement_plan(client_with_snapshot) -> None:
    client, snapshot_id = client_with_snapshot
    await client.post(
        f"/api/snapshots/{snapshot_id}/refine",
        json={"refinement_message": "x"},
    )
    snap_dir = paths.projects_dir() / "p-refine" / "snapshots" / snapshot_id
    refinement_path = snap_dir / "refinement_plan.json"
    assert refinement_path.is_file()
    data = json.loads(refinement_path.read_text(encoding="utf-8"))
    assert data["plan"]["strategy"] == "partial_fix_via_plan_edit"


async def test_refine_endpoint_404_for_unknown_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await run_pending_migrations()

    fake_router = AsyncMock()

    async def fake_build() -> object:
        return fake_router

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/snapshots/nonexistent/refine",
            json={"refinement_message": "x"},
        )
    assert r.status_code == 404


async def test_refine_endpoint_422_on_empty_message(client_with_snapshot) -> None:
    client, snapshot_id = client_with_snapshot
    r = await client.post(
        f"/api/snapshots/{snapshot_id}/refine",
        json={"refinement_message": ""},
    )
    assert r.status_code == 422
