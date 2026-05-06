"""Tests for GET /api/folder/scan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from PIL import Image

from impact_crater.app import create_app
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _photo(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (64, 64), color).save(path, format="JPEG", quality=80)


async def test_scan_lists_supported_media(client: httpx.AsyncClient, tmp_path: Path) -> None:
    _photo(tmp_path / "a.jpg", (200, 80, 30))
    _photo(tmp_path / "b.png", (40, 200, 100))
    (tmp_path / "c.mp4").write_bytes(b"\x00\x00\x00 fake video bytes for ext detection")
    (tmp_path / "ignore.txt").write_text("nope")

    r = await client.get(f"/api/folder/scan?path={tmp_path}")
    assert r.status_code == 200
    body = r.json()
    assert body["photo_count"] == 2
    assert body["video_count"] == 1
    assert body["total_bytes"] > 0
    assert body["truncated"] is False
    types = sorted(it["media_type"] for it in body["items"])
    assert types == ["photo", "photo", "video"]


async def test_scan_recursive(client: httpx.AsyncClient, tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _photo(tmp_path / "a.jpg", (10, 10, 10))
    _photo(sub / "b.jpg", (20, 20, 20))

    r = await client.get(f"/api/folder/scan?path={tmp_path}")
    assert r.status_code == 200
    assert r.json()["photo_count"] == 2


async def test_scan_400_on_missing_path(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    r = await client.get(f"/api/folder/scan?path={tmp_path}/nope")
    assert r.status_code == 400


async def test_scan_400_when_path_is_a_file(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    f = tmp_path / "a.jpg"
    _photo(f, (0, 0, 0))
    r = await client.get(f"/api/folder/scan?path={f}")
    assert r.status_code == 400


async def test_scan_empty_folder_returns_zero_counts(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    r = await client.get(f"/api/folder/scan?path={tmp_path}")
    assert r.status_code == 200
    body = r.json()
    assert body["photo_count"] == 0
    assert body["video_count"] == 0
