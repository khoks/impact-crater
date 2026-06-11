"""Tests for the async job submission API + WebSocket progress stream.

Uses a mocked router (so no real LLM calls) but real ffmpeg if available
for the render path. Skipped when ffmpeg isn't installed.
"""

from __future__ import annotations

import asyncio
import struct
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import numpy as np
import pytest
from impact_crater.app import create_app
from impact_crater.jobs.registry import StageId
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.media import ffmpeg as ff
from impact_crater.pipeline import runner
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations
from PIL import Image

pytestmark = pytest.mark.skipif(
    not ff.has_ffmpeg(), reason="ffmpeg binary not installed"
)


def _photo(path: Path, color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (320, 240), color)
    img.save(path, format="JPEG", quality=80)
    return path.read_bytes()


def _wav(path: Path, *, duration_ms: int = 3000) -> None:
    import math

    sample_rate = 22050
    n = int(sample_rate * duration_ms / 1000)
    amplitude = int(0.2 * 32767)
    frames = bytearray()
    for i in range(n):
        s = int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.extend(struct.pack("<h", s))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))


def _mock_router(photo_paths: list[Path]) -> object:
    import hashlib

    hashes = []
    for p in photo_paths:
        h = hashlib.sha256()
        h.update(p.read_bytes())
        hashes.append(h.hexdigest())

    router = AsyncMock()
    router.set_progress_sink = lambda sink: None
    router.set_telemetry_context = lambda **_: None
    router.caption_image = AsyncMock(return_value="A scene.")
    router.score_image = AsyncMock(return_value=0.7)
    router.embed_image = AsyncMock(return_value=np.ones((768,), dtype=np.float32))
    router.extract_metadata_image = AsyncMock(
        return_value={
            "time_of_day": "midday",
            "people": {"count": 1, "in_focus": []},
            "location": {"description": "outdoor", "lat_long": None},
            "mood": "calm",
            "lighting": "soft",
            "quality": 0.7,
            "foreground_activity": "walk",
            "background_activity": "trees",
            "objects": [],
            "clothing": [],
            "pose_quality_scores": None,
            "generic_tags": ["outdoor"],
            "task_context_tags": [],
            "recognized_persons": [],
        }
    )
    router.judge_narrative_arc = AsyncMock(
        return_value=ArcJudgment(
            selected_items=[
                SelectedItem(
                    candidate_ref=hashes[0],
                    placement_position=0,
                    intended_duration_ms=1000,
                    role="opener",
                ),
                SelectedItem(
                    candidate_ref=hashes[1],
                    placement_position=1,
                    intended_duration_ms=1000,
                    role="closer",
                ),
            ],
            arc_reasoning="warm to cool",
            confidence=0.8,
        )
    )
    return router


@pytest.fixture
async def client_and_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[tuple[httpx.AsyncClient, list[Path], Path]]:
    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")

    photos = [
        tmp_path / "p1.jpg",
        tmp_path / "p2.jpg",
    ]
    _photo(photos[0], (200, 80, 30))
    _photo(photos[1], (40, 200, 100))
    audio = tmp_path / "song.wav"
    _wav(audio)

    fake_router = _mock_router(photos)

    async def fake_build() -> object:
        return fake_router

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    # Reset singleton so each test starts with an empty registry.
    from impact_crater.jobs import registry as registry_mod

    registry_mod.reset_registry_for_tests()

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield (ac, photos, audio)


# ---- Tests -------------------------------------------------------------


async def test_submit_returns_202_with_job_id(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    client, photos, audio = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "warm to cool",
            "target_duration": 2,
            "audio_path": str(audio),
        },
    )
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["state"] in ("queued", "running")
    assert body["websocket_url"].startswith("/api/jobs/ws/")


async def test_submit_400_missing_audio(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path], tmp_path: Path
) -> None:
    client, photos, _ = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(tmp_path / "nope.wav"),
        },
    )
    assert r.status_code == 400


async def test_get_job_returns_404_for_unknown(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    client, _, _ = client_and_paths
    r = await client.get("/api/jobs/nonexistent")
    assert r.status_code == 404


async def test_full_async_flow_succeeds(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    """Submit → poll → eventually `succeeded` with a render_path."""
    client, photos, audio = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(audio),
        },
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # Poll until terminal (or fail loud after 30s).
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["state"] in ("succeeded", "failed", "cancelled"):
            break
        await asyncio.sleep(0.25)
    else:
        pytest.fail("job did not terminate within 30s")

    assert snap["state"] == "succeeded", snap
    assert snap["snapshot_id"]
    assert snap["render_path"]
    assert Path(snap["render_path"]).is_file()


async def test_submit_persists_project_name_and_brief(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    """S-2.9.3: the submit endpoint upserts name + brief onto the projects
    row so the dashboard list shows real labels instead of project-ids."""
    from impact_crater.storage.db import connection

    client, photos, audio = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "warm tones into cool tones",
            "target_duration": 2,
            "audio_path": str(audio),
            "project_name": "Color study",
        },
    )
    assert r.status_code == 202
    project_id = r.json()["project_id"]

    async with connection() as db:
        cursor = await db.execute(
            "SELECT name, brief FROM projects WHERE id = ?", (project_id,)
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row["name"] == "Color study"
    assert row["brief"] == "warm tones into cool tones"

    # GET /api/projects surfaces the same row.
    listed = (await client.get("/api/projects")).json()
    match = next(p for p in listed if p["id"] == project_id)
    assert match["name"] == "Color study"
    assert match["brief"] == "warm tones into cool tones"


async def test_jobs_list_endpoint_returns_session_jobs(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    """S-2.9.2: GET /api/jobs lists every job in this server's registry."""
    client, photos, audio = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "list me",
            "target_duration": 2,
            "audio_path": str(audio),
            "project_name": "Listed job",
        },
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    listed = (await client.get("/api/jobs")).json()
    assert isinstance(listed, list)
    match = next(j for j in listed if j["job_id"] == job_id)
    assert match["project_name"] == "Listed job"
    assert match["brief"] == "list me"
    assert match["state"] in ("queued", "running", "succeeded")

    # Let the background job finish so it doesn't leak into other tests.
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["state"] in ("succeeded", "failed", "cancelled"):
            break
        await asyncio.sleep(0.25)


async def test_registry_records_stage_progress(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    """After a successful run, every stage should be `completed`."""
    client, photos, audio = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(audio),
        },
    )
    job_id = r.json()["job_id"]
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["state"] == "succeeded":
            break
        await asyncio.sleep(0.25)
    assert snap["state"] == "succeeded"
    stage_states = {s["stage"]: s["state"] for s in snap["stages"]}
    expected = [s.value for s in StageId]
    for stage_name in expected:
        assert stage_states[stage_name] == "completed", f"{stage_name}: {stage_states}"


async def test_snapshot_artifacts_served(
    client_and_paths: tuple[httpx.AsyncClient, list[Path], Path],
) -> None:
    client, photos, audio = client_and_paths
    r = await client.post(
        "/api/jobs/submit",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(audio),
        },
    )
    job_id = r.json()["job_id"]
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["state"] == "succeeded":
            break
        await asyncio.sleep(0.25)
    snapshot_id = snap["snapshot_id"]

    mp4 = await client.get(f"/api/snapshots/{snapshot_id}/render.mp4")
    assert mp4.status_code == 200
    assert mp4.headers["content-type"] == "video/mp4"
    assert len(mp4.content) > 0

    cost = await client.get(f"/api/snapshots/{snapshot_id}/cost_summary.json")
    assert cost.status_code == 200
    assert "total_cost_usd" in cost.json()

    plan = await client.get(f"/api/snapshots/{snapshot_id}/plan.json")
    assert plan.status_code == 200
    assert plan.json()["snapshot_id"] == snapshot_id
