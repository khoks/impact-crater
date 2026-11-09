"""Tests for POST /api/snapshots/{id}/refine (open-ended refinement, E-2.12)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from impact_crater import api_auth, paths
from impact_crater.api import snapshots as snapshots_api
from impact_crater.app import create_app
from impact_crater.llm_clients.exceptions import QuotaExceededMidJob
from impact_crater.pipeline import runner
from impact_crater.pipeline.stage6_plan import RenderClip, RenderPlan
from impact_crater.pipeline.stage9_refine import RefinementOutcome, RefinementResult
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def setup_snapshot(tmp_path: Path):
    """Persist a fake snapshot + plan.json + DB row (no source sidecars, so the
    refine executor interprets but doesn't re-render)."""
    await run_pending_migrations()
    project_id = "p-refine"
    snapshot_id = "snap-refine-1"
    snap_dir = paths.projects_dir() / project_id / "snapshots" / snapshot_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    plan = RenderPlan(
        project_id=project_id,
        snapshot_id=snapshot_id,
        target_duration_ms=10_000,
        brief="a zion trip",
        clips=[
            RenderClip(
                candidate_ref="hash-a",
                kind="photo",
                source_path="/tmp/a.jpg",
                intended_duration_ms=5000,
                aspect_ratio_action="as_is",
                role="opener",
            ),
        ],
        arc_reasoning="warm to cool",
        arc_confidence=0.7,
    )
    plan_path = snap_dir / "plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    async with connection() as db:
        await db.execute(
            "INSERT OR IGNORE INTO projects (id, name) VALUES (?, ?)", (project_id, project_id)
        )
        await db.execute(
            "INSERT INTO snapshots (id, project_id, plan_path, render_status) VALUES (?, ?, ?, 'success')",
            (snapshot_id, project_id, str(plan_path)),
        )
        await db.commit()
    return (project_id, snapshot_id, snap_dir)


def _mock_router(outcome: dict) -> object:
    router = AsyncMock()
    router.set_progress_sink = lambda sink: None
    router.set_telemetry_context = lambda **_: None
    router.parse_user_brief = AsyncMock(return_value=outcome)
    return router


@pytest.fixture
async def client_with_snapshot(
    monkeypatch, setup_snapshot
) -> AsyncIterator[tuple[httpx.AsyncClient, str]]:
    _, snapshot_id, _ = setup_snapshot
    fake = _mock_router(
        {
            "interpretation": "shorten the intro",
            "directive_patch": {"positional_rules": [{"region": [0.0, 0.2], "multiplier": 0.7}]},
        }
    )

    async def fake_build() -> object:
        return fake

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        yield (ac, snapshot_id)


async def test_refine_endpoint_returns_interpretation(client_with_snapshot) -> None:
    client, snapshot_id = client_with_snapshot
    r = await client.post(
        f"/api/snapshots/{snapshot_id}/refine", json={"refinement_message": "snappier intro"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["interpretation"] == "shorten the intro"
    assert body["has_directive_patch"] is True
    # No source sidecars → not re-rendered (interpretation still returned).
    assert body["rendered"] is False
    assert body["new_snapshot_id"] is None


async def test_refine_endpoint_explanation(monkeypatch, setup_snapshot) -> None:
    _, snapshot_id, _ = setup_snapshot
    fake = _mock_router({"interpretation": "can't", "explanation": "No snow in the media."})

    async def fake_build() -> object:
        return fake

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        r = await ac.post(
            f"/api/snapshots/{snapshot_id}/refine", json={"refinement_message": "add snow"}
        )
    assert r.status_code == 200
    body = r.json()
    assert "No snow" in body["explanation"]
    assert body["rendered"] is False


async def test_refine_endpoint_persists_refinement_plan(client_with_snapshot) -> None:
    client, snapshot_id = client_with_snapshot
    await client.post(f"/api/snapshots/{snapshot_id}/refine", json={"refinement_message": "x"})
    snap_dir = paths.projects_dir() / "p-refine" / "snapshots" / snapshot_id
    data = json.loads((snap_dir / "refinement_plan.json").read_text(encoding="utf-8"))
    assert data["outcome"]["interpretation"] == "shorten the intro"


async def test_refine_endpoint_404_for_unknown_snapshot(monkeypatch) -> None:
    await run_pending_migrations()

    async def fake_build() -> object:
        return AsyncMock()

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        r = await ac.post("/api/snapshots/nonexistent/refine", json={"refinement_message": "x"})
    assert r.status_code == 404


async def test_refine_endpoint_422_on_empty_message(client_with_snapshot) -> None:
    client, snapshot_id = client_with_snapshot
    r = await client.post(f"/api/snapshots/{snapshot_id}/refine", json={"refinement_message": ""})
    assert r.status_code == 422


async def test_refine_records_the_request_on_parent_and_child(monkeypatch, setup_snapshot) -> None:
    project_id, snapshot_id, snap_dir = setup_snapshot

    async def fake_build() -> object:
        return object()

    async def fake_execute(_router, *, project_id, prior_plan, refinement_message):
        async with connection() as db:
            await db.execute(
                "INSERT INTO snapshots (id, project_id, parent_snapshot_id, plan_path, "
                "render_status) VALUES (?, ?, ?, ?, 'success')",
                ("snap-child", project_id, prior_plan.snapshot_id, str(child_plan)),
            )
            await db.commit()
        return RefinementResult(
            outcome=RefinementOutcome(interpretation="tighter middle"),
            new_snapshot_id="snap-child",
            rendered=True,
        )

    child_dir = paths.projects_dir() / project_id / "snapshots" / "snap-child"
    child_dir.mkdir(parents=True, exist_ok=True)
    child_plan = child_dir / "plan.json"
    child_plan.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)
    monkeypatch.setattr(snapshots_api, "execute_refinement", fake_execute)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        r = await ac.post(
            f"/api/snapshots/{snapshot_id}/refine",
            json={"refinement_message": "shorter middle part"},
        )
        assert r.status_code == 200
        assert r.json()["new_snapshot_id"] == "snap-child"

        parent_record = json.loads((snap_dir / "refinement_plan.json").read_text("utf-8"))
        child_record = json.loads((child_dir / "refined_from.json").read_text("utf-8"))
        assert parent_record == child_record
        assert child_record["refinement_message"] == "shorter middle part"
        assert child_record["parent_snapshot_id"] == snapshot_id

        child = (await ac.get("/api/snapshots/snap-child")).json()
        assert child["parent_snapshot_id"] == snapshot_id
        assert child["refinement_message"] == "shorter middle part"
        assert child["refinement_interpretation"] == "tighter middle"
        assert child["children"] == []

        parent = (await ac.get(f"/api/snapshots/{snapshot_id}")).json()
        assert parent["parent_snapshot_id"] is None
        assert parent["children"] == ["snap-child"]
        assert parent["refinement_message"] is None
        assert parent["project_name"] == project_id


async def test_snapshot_detail_404(client_with_snapshot) -> None:
    client, _ = client_with_snapshot
    r = await client.get("/api/snapshots/nope")
    assert r.status_code == 404


async def test_refine_stopped_by_the_spend_cap_is_a_402_with_the_reason(
    monkeypatch, setup_snapshot
) -> None:
    _, snapshot_id, _ = setup_snapshot

    async def fake_build() -> object:
        return object()

    async def halted(*_args, **_kwargs):
        raise QuotaExceededMidJob(
            reason="total_cap_would_be_exceeded",
            provider="anthropic",
            spent_usd=4.9,
            cap_usd=5.0,
            estimate_usd=0.5,
        )

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)
    monkeypatch.setattr(snapshots_api, "execute_refinement", halted)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        r = await ac.post(
            f"/api/snapshots/{snapshot_id}/refine", json={"refinement_message": "re-judge it"}
        )
    assert r.status_code == 402
    assert r.json()["detail"].startswith(
        "Stopped at your daily spend cap: $4.90 of your $5.00 total"
    )
