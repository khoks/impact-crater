"""Tests for POST /api/jobs/render with mocked router + real ffmpeg."""

from __future__ import annotations

import struct
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import numpy as np
import pytest
from PIL import Image

from impact_crater.app import create_app
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.media import ffmpeg as ff
from impact_crater.pipeline import runner
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations

pytestmark = pytest.mark.skipif(
    not ff.has_ffmpeg(), reason="ffmpeg binary not installed"
)


def _photo(tmp_path: Path, name: str, color: tuple[int, int, int]) -> Path:
    img = Image.new("RGB", (640, 480), color)
    p = tmp_path / name
    img.save(p, format="JPEG", quality=85)
    return p


def _wav(tmp_path: Path, *, duration_ms: int = 3000) -> Path:
    """440 Hz tone — silence-only WAVs make loudnorm produce NaN."""
    import math

    p = tmp_path / "song.wav"
    sample_rate = 22050
    n = int(sample_rate * duration_ms / 1000)
    amplitude = int(0.2 * 32767)
    frames = bytearray()
    for i in range(n):
        sample = int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))
    return p


def _mock_router_for_full_pipeline() -> object:
    """Mock router that drives every M1 LLM call; ffmpeg runs for real."""
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
    return router


async def _score_by_dim(*args, **kwargs) -> float:
    return 0.7 if kwargs.get("dimension") == "quality" else 0.6


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")

    fake_router = _mock_router_for_full_pipeline()

    # The arc judgment must reference content_hashes that exist post-ingest.
    # We pre-compute the SHA-256 of two test photos and stuff them into the
    # mock so the candidate_refs resolve cleanly during plan compile.
    photo_paths = [_photo(tmp_path, "p1.jpg", (200, 80, 30)), _photo(tmp_path, "p2.jpg", (40, 200, 100))]
    import hashlib

    hashes = []
    for p in photo_paths:
        h = hashlib.sha256()
        h.update(p.read_bytes())
        hashes.append(h.hexdigest())

    fake_router.judge_narrative_arc = AsyncMock(
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
            confidence=0.7,
        )
    )

    async def fake_build() -> object:
        return fake_router

    monkeypatch.setattr(runner, "build_router_from_settings", fake_build)

    # Stash the prepared paths on the client so tests can read them.
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._test_photo_paths = photo_paths  # type: ignore[attr-defined]
        ac._test_hashes = hashes  # type: ignore[attr-defined]
        yield ac


# ---- Tests -------------------------------------------------------------


async def test_render_endpoint_produces_mp4(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    audio = _wav(tmp_path, duration_ms=3000)
    photos: list[Path] = client._test_photo_paths  # type: ignore[attr-defined]

    r = await client.post(
        "/api/jobs/render",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "warm to cool",
            "target_duration": 2,
            "audio_path": str(audio),
        },
        timeout=120.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["media_count"] == 2
    assert Path(body["render_path"]).is_file()
    assert body["output_bytes"] > 0
    assert Path(body["cost_summary_path"]).is_file()
    assert body["arc_judgment"]["confidence"] == pytest.approx(0.7)
    # ffprobe-validate the render.
    probe = ff.run_ffprobe(
        ["-v", "error", "-show_format", "-show_streams", "-print_format", "json",
         body["render_path"]]
    )
    import json
    parsed = json.loads(probe.stdout.decode("utf-8"))
    assert any(s["codec_type"] == "video" for s in parsed["streams"])
    assert any(s["codec_type"] == "audio" for s in parsed["streams"])


async def test_render_endpoint_rejects_music_video_at_m2(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    audio = _wav(tmp_path)
    photos: list[Path] = client._test_photo_paths  # type: ignore[attr-defined]
    r = await client.post(
        "/api/jobs/render",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(audio),
            "mode": "music_video",
        },
    )
    assert r.status_code == 501
    assert "M4" in r.json()["detail"]


async def test_render_endpoint_400_for_missing_audio(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    photos: list[Path] = client._test_photo_paths  # type: ignore[attr-defined]
    r = await client.post(
        "/api/jobs/render",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(tmp_path / "nope.wav"),
        },
    )
    assert r.status_code == 400


async def test_render_endpoint_402_on_quota_denial(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "0.01")
    audio = _wav(tmp_path)
    photos: list[Path] = client._test_photo_paths  # type: ignore[attr-defined]
    r = await client.post(
        "/api/jobs/render",
        json={
            "media_paths": [str(p) for p in photos],
            "brief": "x",
            "target_duration": 2,
            "audio_path": str(audio),
        },
    )
    assert r.status_code == 402
    assert r.json()["detail"]["reason"] == "total_cap_would_be_exceeded"
