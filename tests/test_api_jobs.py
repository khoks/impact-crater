"""Tests for POST /api/jobs/headless.

The router is monkey-patched at the runner.build_router_from_settings()
level so we don't hit real APIs in unit tests; the integration test
(tests/integration/test_full_headless_pipeline.py) exercises the real
provider path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import numpy as np
import pytest
from PIL import Image

from impact_crater.app import create_app
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.pipeline import runner
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations


def _photo(tmp_path: Path, name: str, color: tuple[int, int, int]) -> Path:
    img = Image.new("RGB", (320, 240), color)
    p = tmp_path / name
    img.save(p, format="JPEG", quality=80)
    return p


def _mock_router_factory() -> object:
    """A factory that returns the same canned-response router every call."""
    router = AsyncMock()
    router.caption_image = AsyncMock(return_value="A scene.")
    router.score_image = AsyncMock(side_effect=_score_by_dim)
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
                    candidate_ref="x",
                    placement_position=0,
                    intended_duration_ms=2000,
                    role="opener",
                )
            ],
            arc_reasoning="basic arc",
            confidence=0.7,
        )
    )
    return router


async def _score_by_dim(*args, **kwargs) -> float:
    return 0.7 if kwargs.get("dimension") == "quality" else 0.6


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")

    fake_router = _mock_router_factory()

    async def fake_build() -> object:
        return fake_router

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_headless_endpoint_returns_arc_judgment(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    paths = [
        str(_photo(tmp_path, "p1.jpg", (200, 80, 30))),
        str(_photo(tmp_path, "p2.jpg", (40, 200, 100))),
    ]
    r = await client.post(
        "/api/jobs/headless",
        json={
            "media_paths": paths,
            "brief": "test brief",
            "target_duration": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["media_count"] == 2
    assert body["candidate_count"] >= 1
    assert body["arc_judgment"]["confidence"] == pytest.approx(0.7)
    assert body["arc_judgment"]["selected_items"][0]["role"] == "opener"
    assert body["candidate_set"]["target_size"] >= 1
    assert body["quota"]["allowed"] is True


async def test_headless_endpoint_rejects_empty_media_paths(
    client: httpx.AsyncClient,
) -> None:
    r = await client.post(
        "/api/jobs/headless",
        json={"media_paths": [], "brief": "x", "target_duration": 10},
    )
    assert r.status_code == 422


async def test_headless_endpoint_returns_402_on_quota_denial(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    # Set the cap below the per-asset estimate.
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "0.01")
    paths = [str(_photo(tmp_path, "p1.jpg", (200, 80, 30)))]
    r = await client.post(
        "/api/jobs/headless",
        json={
            "media_paths": paths,
            "brief": "test brief",
            "target_duration": 10,
        },
    )
    assert r.status_code == 402
    body = r.json()
    assert body["detail"]["reason"] == "total_cap_would_be_exceeded"


async def test_headless_endpoint_passes_overrides(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    paths = [str(_photo(tmp_path, "p1.jpg", (200, 80, 30)))]
    r = await client.post(
        "/api/jobs/headless",
        json={
            "media_paths": paths,
            "brief": "test brief",
            "target_duration": 10,
            "quality_threshold": 0.0,
            "target_size": 1,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["candidate_set"]["target_size"] == 1


async def test_headless_endpoint_412_when_no_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the router factory raises (e.g. missing keys), API returns 412."""
    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")

    async def fake_build() -> object:
        raise RuntimeError("missing api keys")

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    paths = [str(_photo(tmp_path, "p1.jpg", (200, 80, 30)))]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/jobs/headless",
            json={
                "media_paths": paths,
                "brief": "x",
                "target_duration": 10,
            },
        )
    assert r.status_code == 412
    assert "missing api keys" in r.json()["detail"]
