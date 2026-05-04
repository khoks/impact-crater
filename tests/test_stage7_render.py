"""Stage 7 render tests — actual ffmpeg invocations, ffprobe-validated output.

Skipped when the ffmpeg binary is not available. Real but fast — uses
2-3 small synthetic photos + a short synthetic WAV; full pipeline
takes a few seconds.
"""

from __future__ import annotations

import json
import struct
import wave
from pathlib import Path

import pytest
from PIL import Image

from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.media import ffmpeg as ff
from impact_crater.pipeline import stage6_plan, stage7_render
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.stage6_plan import StandardMusicSpec
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations

pytestmark = pytest.mark.skipif(
    not ff.has_ffmpeg(), reason="ffmpeg binary not installed"
)


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


def _photo_file(tmp_path: Path, name: str, color: tuple[int, int, int]) -> Path:
    img = Image.new("RGB", (640, 480), color)
    p = tmp_path / name
    img.save(p, format="JPEG", quality=85)
    return p


def _photo_record(path: Path, content_hash: str, *, width: int = 640, height: int = 480) -> MediaRecord:
    return MediaRecord(
        content_hash=content_hash,
        source_path=str(path),
        media_type="photo",
        file_size=path.stat().st_size,
        quick_stats={"width": width, "height": height, "phash": "00", "dhash": "00"},
    )


def _synthetic_wav(path: Path, *, duration_ms: int, sample_rate: int = 22050) -> None:
    """Write a 1-channel WAV with a 440 Hz tone of `duration_ms` length."""
    import math

    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = int(0.2 * 32767)
    frames = bytearray()
    for i in range(n_samples):
        sample = int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))


def _ffprobe_video(path: Path) -> dict:
    cp = ff.run_ffprobe(
        [
            "-v", "error",
            "-show_format", "-show_streams",
            "-print_format", "json",
            str(path),
        ]
    )
    return json.loads(cp.stdout.decode("utf-8"))


# ---- Tests -------------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_render_two_photos_no_audio(tmp_path: Path) -> None:
    """Smallest happy path: two photos, no music, ~2s video."""
    p1 = _photo_file(tmp_path, "p1.jpg", (200, 80, 30))
    p2 = _photo_file(tmp_path, "p2.jpg", (40, 200, 100))
    arc = ArcJudgment(
        selected_items=[
            SelectedItem(candidate_ref="h1", placement_position=0, intended_duration_ms=1000, role="opener"),
            SelectedItem(candidate_ref="h2", placement_position=1, intended_duration_ms=1000, role="closer"),
        ],
        arc_reasoning="warm to cool",
        confidence=0.7,
    )
    plan = await stage6_plan.compile_plan(
        arc_judgment=arc,
        ingest_records=[_photo_record(p1, "h1"), _photo_record(p2, "h2")],
        project_id="render-photos",
        target_duration_seconds=2,
    )
    result = await stage7_render.render_plan(plan, correlation_id="cid-1")
    assert result.status == "success"
    out = Path(result.render_path)
    assert out.is_file()
    assert out.stat().st_size > 0

    # ffprobe-verify: 1920x1080 H.264 yuv420p, ~2s.
    probe = _ffprobe_video(out)
    video_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    assert len(video_streams) == 1
    v = video_streams[0]
    assert v["codec_name"] == "h264"
    assert v["width"] == 1920
    assert v["height"] == 1080
    assert v["pix_fmt"] == "yuv420p"
    duration_s = float(probe["format"]["duration"])
    assert 1.5 <= duration_s <= 2.5


@pytest.mark.usefixtures("db_initialized")
async def test_render_with_music_normalizes_audio(tmp_path: Path) -> None:
    """Render with music: output has video + audio, fade-in/out applied, ~2s."""
    p = _photo_file(tmp_path, "p.jpg", (10, 100, 200))
    wav = tmp_path / "song.wav"
    _synthetic_wav(wav, duration_ms=4000)  # 4s of audio, target 2s → trimmed

    arc = ArcJudgment(
        selected_items=[
            SelectedItem(candidate_ref="h", placement_position=0, intended_duration_ms=2000, role="opener"),
        ],
        arc_reasoning="single shot",
        confidence=0.6,
    )
    music = StandardMusicSpec(
        audio_path=str(wav),
        audio_duration_ms=4000,
        fade_in_ms=300,
        fade_out_ms=300,
    )
    plan = await stage6_plan.compile_plan(
        arc_judgment=arc,
        ingest_records=[_photo_record(p, "h")],
        project_id="render-music",
        target_duration_seconds=2,
        audio=music,
    )
    result = await stage7_render.render_plan(plan, correlation_id="cid-music")
    assert result.status == "success"
    out = Path(result.render_path)
    probe = _ffprobe_video(out)
    audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    video_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    assert len(video_streams) == 1
    assert len(audio_streams) == 1
    assert audio_streams[0]["codec_name"] in ("aac", "aac_lc")
    duration_s = float(probe["format"]["duration"])
    assert 1.5 <= duration_s <= 2.5


@pytest.mark.usefixtures("db_initialized")
async def test_render_updates_snapshot_render_status(tmp_path: Path) -> None:
    p = _photo_file(tmp_path, "p.jpg", (100, 100, 100))
    arc = ArcJudgment(
        selected_items=[
            SelectedItem(candidate_ref="h", placement_position=0, intended_duration_ms=1000, role="opener"),
        ],
        arc_reasoning="x",
        confidence=0.5,
    )
    plan = await stage6_plan.compile_plan(
        arc_judgment=arc,
        ingest_records=[_photo_record(p, "h")],
        project_id="render-status",
        target_duration_seconds=1,
    )
    result = await stage7_render.render_plan(plan, correlation_id="cid-status")
    async with connection() as db:
        cursor = await db.execute(
            "SELECT render_status, render_path FROM snapshots WHERE id = ?",
            (plan.snapshot_id,),
        )
        row = await cursor.fetchone()
    assert row["render_status"] == "success"
    assert row["render_path"] == result.render_path


@pytest.mark.usefixtures("db_initialized")
async def test_render_emits_render_event_telemetry(tmp_path: Path) -> None:
    from impact_crater import telemetry

    p = _photo_file(tmp_path, "p.jpg", (10, 100, 50))
    arc = ArcJudgment(
        selected_items=[
            SelectedItem(candidate_ref="h", placement_position=0, intended_duration_ms=1000, role="opener"),
        ],
        arc_reasoning="x",
        confidence=0.5,
    )
    plan = await stage6_plan.compile_plan(
        arc_judgment=arc,
        ingest_records=[_photo_record(p, "h")],
        project_id="render-telemetry",
        target_duration_seconds=1,
    )
    await stage7_render.render_plan(plan, correlation_id="cid-tele")
    events = telemetry.events_for_correlation("cid-tele")
    render_events = [e for e in events if e.get("event_type") == "render"]
    assert len(render_events) == 1
    assert render_events[0]["render_status"] == "success"
    assert render_events[0]["output_bytes"] > 0


@pytest.mark.usefixtures("db_initialized")
async def test_render_failure_updates_snapshot_to_failure_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bogus source path makes pre-render fail; verify status transitions."""
    arc = ArcJudgment(
        selected_items=[
            SelectedItem(
                candidate_ref="h-bogus",
                placement_position=0,
                intended_duration_ms=1000,
                role="opener",
            ),
        ],
        arc_reasoning="x",
        confidence=0.5,
    )
    bogus = MediaRecord(
        content_hash="h-bogus",
        source_path=str(tmp_path / "nope.jpg"),
        media_type="photo",
        file_size=0,
        quick_stats={"width": 1920, "height": 1080},
    )
    plan = await stage6_plan.compile_plan(
        arc_judgment=arc,
        ingest_records=[bogus],
        project_id="render-fail",
        target_duration_seconds=1,
    )
    with pytest.raises(stage7_render.RenderError):
        await stage7_render.render_plan(plan, correlation_id="cid-fail")
    async with connection() as db:
        cursor = await db.execute(
            "SELECT render_status FROM snapshots WHERE id = ?", (plan.snapshot_id,)
        )
        row = await cursor.fetchone()
    assert row["render_status"] == "failure"
