"""Tests for the feedback capture API + JSONL mirror (A-023)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from impact_crater import paths
from impact_crater.app import create_app
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_post_feedback_persists_and_mirrors_jsonl(client: httpx.AsyncClient) -> None:
    payload = {
        "phase": "stage_4_prefilter",
        "verdict": "incorrect",
        "snapshot_id": "snap-1",
        "project_id": "proj-1",
        "decision_ref": "drop:semantic_duplicate",
        "content_hash": "abc123",
        "comment": "This shot was the best of the burst — shouldn't have been dropped.",
        "context": {"reason": "semantic_duplicate", "kept_key": "def456"},
    }
    r = await client.post("/api/feedback", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] >= 1
    assert body["status"] == "new"

    # Readable back via the list endpoint.
    listed = (await client.get("/api/feedback")).json()
    assert len(listed) == 1
    item = listed[0]
    assert item["verdict"] == "incorrect"
    assert item["phase"] == "stage_4_prefilter"
    assert item["content_hash"] == "abc123"
    assert item["status"] == "new"

    # Mirrored to ~/.impact-crater/feedback.jsonl for Claude pickup.
    jsonl = paths.home() / "feedback.jsonl"
    assert jsonl.is_file()
    lines = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line]
    assert lines[-1]["comment"].startswith("This shot was the best")
    assert lines[-1]["context"]["reason"] == "semantic_duplicate"


async def test_feedback_saves_screenshot(client: httpx.AsyncClient) -> None:
    # 1x1 transparent PNG.
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    r = await client.post(
        "/api/feedback",
        json={
            "phase": "stage_5_judge",
            "verdict": "different",
            "comment": "wrong opener",
            "screenshot_data_url": f"data:image/png;base64,{png_b64}",
        },
    )
    assert r.status_code == 201
    fid = r.json()["id"]
    # The screenshot is served back.
    shot = await client.get(f"/api/feedback/{fid}/screenshot.png")
    assert shot.status_code == 200
    assert shot.headers["content-type"] == "image/png"
    assert len(shot.content) > 0
    # And it's on disk for Claude pickup.
    saved = paths.home() / "feedback_screenshots" / f"{fid}.png"
    assert saved.is_file()


async def test_feedback_without_screenshot_has_no_file(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/feedback", json={"phase": "cast", "verdict": "correct"}
    )
    fid = r.json()["id"]
    shot = await client.get(f"/api/feedback/{fid}/screenshot.png")
    assert shot.status_code == 404


async def test_feedback_filters_by_status_and_snapshot(client: httpx.AsyncClient) -> None:
    for i in range(3):
        await client.post(
            "/api/feedback",
            json={
                "phase": "stage_5_judge",
                "verdict": "different",
                "snapshot_id": f"snap-{i}",
                "comment": f"note {i}",
            },
        )
    all_items = (await client.get("/api/feedback")).json()
    assert len(all_items) == 3
    one = (await client.get("/api/feedback", params={"snapshot_id": "snap-1"})).json()
    assert len(one) == 1
    assert one[0]["snapshot_id"] == "snap-1"
    new_only = (await client.get("/api/feedback", params={"status_filter": "new"})).json()
    assert len(new_only) == 3


async def test_feedback_rejects_bad_verdict(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/feedback",
        json={"phase": "stage_4_prefilter", "verdict": "maybe"},
    )
    assert r.status_code == 422


async def test_media_thumb_404_for_unknown_hash(client: httpx.AsyncClient, tmp_path: Path) -> None:
    r = await client.get("/api/media/" + "a" * 32 + "/thumb.jpg")
    assert r.status_code == 404


async def test_media_thumb_rejects_bad_hash(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/media/not-a-hash!/thumb.jpg")
    assert r.status_code in (400, 404)
