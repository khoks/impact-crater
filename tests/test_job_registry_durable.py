"""The job registry survives a server restart (S-2.9.19).

A "restart" here is a fresh `JobRegistry` (or a reset singleton) reading the
same SQLite `jobs` table the previous one wrote.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from impact_crater import api_auth
from impact_crater.app import create_app
from impact_crater.jobs import registry as registry_mod
from impact_crater.jobs.registry import (
    INTERRUPTED_REASON,
    JobRegistry,
    JobSnapshot,
    StageId,
)
from impact_crater.storage.migrations import run_pending_migrations
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
async def _migrated() -> AsyncIterator[None]:
    await run_pending_migrations()
    registry_mod.reset_registry_for_tests()
    yield
    registry_mod.reset_registry_for_tests()


async def _finished_job(registry: JobRegistry, job_id: str, submitted_at: str) -> None:
    await registry.register(
        JobSnapshot(job_id=job_id, project_id="p1", project_name="Zion", submitted_at=submitted_at)
    )
    await registry.update_state(job_id, "running")
    await registry.update_stage(job_id, StageId.INGEST, state="running")
    await registry.record_llm_call(
        job_id, operation="score", provider="anthropic", tier="S", cost_usd=0.25, cache_hit=False
    )
    await registry.update_stage(job_id, StageId.INGEST, state="completed", detail="55 files")
    await registry.update_state(job_id, "succeeded", snapshot_id="snap-1", render_path="/r.mp4")


async def test_a_finished_job_is_loaded_back_after_a_restart() -> None:
    await _finished_job(JobRegistry(), "j1", "2026-11-08T10:00:00+00:00")

    after = JobRegistry()
    assert after.get("j1") is None
    snap = await after.get_or_load("j1")
    assert snap is not None
    assert snap.state == "succeeded"
    assert snap.snapshot_id == "snap-1"
    assert snap.project_name == "Zion"
    assert snap.total_cost_usd == pytest.approx(0.25)
    ingest = next(s for s in snap.stages if s.stage == StageId.INGEST.value)
    assert (ingest.state, ingest.detail) == ("completed", "55 files")
    assert after.get("j1") is snap
    assert await after.get_or_load("nope") is None


async def test_recovery_marks_cut_off_jobs_interrupted_and_leaves_finished_ones() -> None:
    before = JobRegistry()
    await _finished_job(before, "done", "2026-11-08T09:00:00+00:00")
    await before.register(JobSnapshot(job_id="cut", project_id="p1"))
    await before.update_state("cut", "running")
    await before.update_stage("cut", StageId.INGEST, state="completed")
    await before.update_stage("cut", StageId.BULK_OPS, state="running")
    await before.register(JobSnapshot(job_id="waiting", project_id="p1"))

    after = JobRegistry()
    assert sorted(await after.recover_interrupted()) == ["cut", "waiting"]

    cut = after.get("cut")
    assert cut is not None
    assert cut.state == "failed"
    assert cut.failure_reason == INTERRUPTED_REASON
    assert cut.completed_at is not None
    states = {s.stage: (s.state, s.detail) for s in cut.stages}
    assert states[StageId.INGEST.value] == ("completed", "")
    assert states[StageId.BULK_OPS.value] == ("failed", "interrupted by a server restart")

    third = JobRegistry()
    assert await third.recover_interrupted() == []
    done = await third.get_or_load("done")
    assert done is not None and done.state == "succeeded"
    reloaded = await third.get_or_load("cut")
    assert reloaded is not None and reloaded.failure_reason == INTERRUPTED_REASON


async def test_recent_is_newest_first_and_prefers_the_live_object() -> None:
    registry = JobRegistry()
    for i in range(3):
        await registry.register(
            JobSnapshot(job_id=f"j{i}", project_id="p", submitted_at=f"2026-11-0{i + 1}T00:00:00")
        )
    live = registry.get("j2")
    assert live is not None
    live.total_cost_usd = 9.0  # cost counters move between saves

    recent = await registry.recent(2)
    assert [s.job_id for s in recent] == ["j2", "j1"]
    assert recent[0] is live
    assert [s.job_id for s in await JobRegistry().recent(5)] == ["j2", "j1", "j0"]


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1", headers=api_auth.auth_header()
    ) as ac:
        yield ac


async def test_job_pages_resolve_after_a_restart(client: httpx.AsyncClient) -> None:
    await _finished_job(registry_mod.get_registry(), "j1", "2026-11-08T10:00:00+00:00")
    registry_mod.reset_registry_for_tests()

    r = await client.get("/api/jobs/j1")
    assert r.status_code == 200
    assert r.json()["state"] == "succeeded"
    assert r.json()["snapshot_id"] == "snap-1"
    assert [j["job_id"] for j in (await client.get("/api/jobs")).json()] == ["j1"]
    assert (await client.post("/api/jobs/j1/cancel")).status_code == 409
    assert (await client.get("/api/jobs/missing")).status_code == 404


def test_websocket_replays_a_reloaded_job_and_closes() -> None:
    asyncio.run(_finished_job(JobRegistry(), "j1", "2026-11-08T10:00:00+00:00"))
    client = TestClient(create_app(), base_url="http://127.0.0.1")
    with client.websocket_connect("ws://127.0.0.1/api/jobs/ws/j1") as ws:
        ws.send_json({"type": "auth", "token": api_auth.get_or_create_token()})
        first = ws.receive_json()
        assert first["type"] == "state"
        assert first["payload"]["state"] == "succeeded"
        assert first["payload"]["snapshot_id"] == "snap-1"


def test_startup_marks_a_job_the_last_shutdown_cut_off() -> None:
    async def _cut_off() -> None:
        before = JobRegistry()
        await before.register(JobSnapshot(job_id="cut", project_id="p1"))
        await before.update_state("cut", "running")

    asyncio.run(_cut_off())
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        body = client.get("/api/jobs/cut", headers=api_auth.auth_header()).json()
    assert body["state"] == "failed"
    assert body["failure_reason"] == INTERRUPTED_REASON
