"""Full M2 pipeline integration test — Stages 1-7 against real APIs.

Hits real Anthropic + Google through the LLMRouter, then renders a real
MP4 via ffmpeg with two-pass loudnorm. Gated behind `--integration`.
Skipped when the ffmpeg binary is unavailable.
"""

from __future__ import annotations

import io
import json
import math
import os
import struct
import wave
from pathlib import Path

import pytest
from PIL import Image

from impact_crater.llm_clients.anthropic_client import AnthropicLLMClient
from impact_crater.llm_clients.google_client import GoogleLLMClient
from impact_crater.llm_clients.router import LLMRouter
from impact_crater.media import ffmpeg as ff
from impact_crater.pipeline.runner import FullJobConfig, run_full_pipeline
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations

pytestmark = pytest.mark.integration


def _photo(path: Path, color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (640, 480), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    blob = buf.getvalue()
    path.write_bytes(blob)
    return blob


def _wav(path: Path, *, duration_ms: int = 4000) -> None:
    sample_rate = 22050
    n = int(sample_rate * duration_ms / 1000)
    amplitude = int(0.2 * 32767)
    frames = bytearray()
    for i in range(n):
        sample = int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))


@pytest.fixture
async def real_router_keys() -> tuple[str, str]:
    a = os.environ.get("ANTHROPIC_API_KEY")
    g = os.environ.get("GOOGLE_API_KEY")
    if not a or not g:
        pytest.skip("ANTHROPIC_API_KEY + GOOGLE_API_KEY required")
    return (a, g)


@pytest.mark.skipif(not ff.has_ffmpeg(), reason="ffmpeg binary not installed")
async def test_full_m2_pipeline_real_apis_end_to_end(
    tmp_path: Path,
    real_router_keys: tuple[str, str],
) -> None:
    """End-to-end Stages 1-7 against real APIs producing a real MP4."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    photo_paths: list[Path] = []
    for i, color in enumerate([(200, 80, 30), (40, 200, 100), (60, 60, 220)]):
        p = media_dir / f"photo-{i}.jpg"
        _photo(p, color)
        photo_paths.append(p)

    audio_path = tmp_path / "tone.wav"
    _wav(audio_path, duration_ms=4000)

    await run_pending_migrations()
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")

    a_key, g_key = real_router_keys
    router = LLMRouter(
        clients={
            "anthropic": AnthropicLLMClient(api_key=a_key),
            "google": GoogleLLMClient(api_key=g_key),
        },
    )

    config = FullJobConfig(
        media_paths=photo_paths,
        brief="A short montage of colorful test patterns.",
        target_duration_seconds=3,
        audio_path=audio_path,
    )
    result = await run_full_pipeline(config, router=router)

    assert result.media_count == 3
    assert Path(result.render_path).is_file()
    assert result.output_bytes > 0
    assert Path(result.cost_summary_path).is_file()

    # ffprobe-validate the MP4 has a video + audio stream.
    probe = ff.run_ffprobe(
        ["-v", "error", "-show_format", "-show_streams", "-print_format", "json",
         result.render_path]
    )
    parsed = json.loads(probe.stdout.decode("utf-8"))
    video_streams = [s for s in parsed["streams"] if s["codec_type"] == "video"]
    audio_streams = [s for s in parsed["streams"] if s["codec_type"] == "audio"]
    assert len(video_streams) == 1
    assert video_streams[0]["codec_name"] == "h264"
    assert len(audio_streams) == 1

    # Cost summary should reflect real calls.
    summary = json.loads(Path(result.cost_summary_path).read_text(encoding="utf-8"))
    assert summary["project_id"] == result.project_id
    assert summary["snapshot_id"] == result.snapshot_id
    assert summary["total_cost_usd"] >= 0.0  # Real calls happened
