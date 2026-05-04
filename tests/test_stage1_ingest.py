"""Tests for Stage 1 ingest — content-hash, photo/video paths, idempotency."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from impact_crater import paths as paths_mod
from impact_crater.pipeline import stage1_ingest
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


# ---- Fixtures ----------------------------------------------------------


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


@pytest.fixture
def synthetic_jpeg(tmp_path: Path) -> Path:
    """A unique solid-color JPEG written to a tmp file."""
    img = Image.new("RGB", (320, 240), (200, 80, 30))
    out = tmp_path / "photo.jpg"
    img.save(out, format="JPEG", quality=82)
    return out


@pytest.fixture
def synthetic_png(tmp_path: Path) -> Path:
    img = Image.new("RGB", (200, 200), (40, 200, 100))
    out = tmp_path / "photo2.png"
    img.save(out, format="PNG")
    return out


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    """A 2-second 320x240 MP4 generated via cv2.VideoWriter (mp4v fourcc).

    Each second is a different solid color, so scenedetect's ContentDetector
    will see a real cut and produce two scenes.
    """
    import cv2

    out = tmp_path / "video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 24
    width, height = 320, 240
    writer = cv2.VideoWriter(str(out), fourcc, fps, (width, height))
    if not writer.isOpened():
        pytest.skip("cv2 mp4v VideoWriter not available in this environment")
    # Section A: solid red for 1 second
    red = np.full((height, width, 3), (40, 40, 220), dtype=np.uint8)
    for _ in range(fps):
        writer.write(red)
    # Section B: solid blue for 1 second
    blue = np.full((height, width, 3), (220, 80, 40), dtype=np.uint8)
    for _ in range(fps):
        writer.write(blue)
    writer.release()
    if not out.is_file() or out.stat().st_size == 0:
        pytest.skip("synthetic video write failed; cv2 codec missing")
    return out


# ---- Content-hash + classification ------------------------------------


def test_classify_photo_extensions(tmp_path: Path) -> None:
    for ext in [".jpg", ".jpeg", ".png", ".webp", ".heic"]:
        assert stage1_ingest._classify(tmp_path / f"x{ext}") == "photo"


def test_classify_video_extensions(tmp_path: Path) -> None:
    for ext in [".mp4", ".mov", ".mkv", ".webm"]:
        assert stage1_ingest._classify(tmp_path / f"x{ext}") == "video"


def test_classify_unknown_returns_none(tmp_path: Path) -> None:
    assert stage1_ingest._classify(tmp_path / "x.txt") is None


def test_sha256_of_known_bytes(tmp_path: Path) -> None:
    p = tmp_path / "hash-target.bin"
    p.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert stage1_ingest._sha256_file(p) == expected


# ---- Photo ingest ------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_photo_writes_row_and_thumbnails(
    synthetic_jpeg: Path,
) -> None:
    records = await stage1_ingest.ingest_media("proj-A", [synthetic_jpeg])
    assert len(records) == 1
    rec = records[0]
    assert rec.media_type == "photo"
    assert rec.file_size == synthetic_jpeg.stat().st_size
    assert "phash" in rec.quick_stats and "dhash" in rec.quick_stats
    assert rec.thumb_256_path and Path(rec.thumb_256_path).is_file()
    assert rec.thumb_1024_path and Path(rec.thumb_1024_path).is_file()

    async with connection() as db:
        cursor = await db.execute(
            "SELECT media_type, file_size FROM media WHERE content_hash = ?",
            (rec.content_hash,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row["media_type"] == "photo"


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_writes_source_sidecar(synthetic_jpeg: Path) -> None:
    records = await stage1_ingest.ingest_media("proj-A", [synthetic_jpeg])
    rec = records[0]
    sidecar = (
        paths_mod.projects_dir() / "proj-A" / "sources" / f"{rec.content_hash}.json"
    )
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["content_hash"] == rec.content_hash
    assert payload["media_type"] == "photo"
    assert payload["quick_stats"]["width"] == 320
    assert payload["quick_stats"]["height"] == 240


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_is_idempotent(synthetic_jpeg: Path) -> None:
    """Re-running ingest produces same content_hash and only one media row."""
    r1 = await stage1_ingest.ingest_media("proj-A", [synthetic_jpeg])
    r2 = await stage1_ingest.ingest_media("proj-A", [synthetic_jpeg])
    assert r1[0].content_hash == r2[0].content_hash

    async with connection() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM media WHERE content_hash = ?",
            (r1[0].content_hash,),
        )
        row = await cursor.fetchone()
    assert row["c"] == 1


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_multiple_photos_share_project_join(
    synthetic_jpeg: Path, synthetic_png: Path
) -> None:
    records = await stage1_ingest.ingest_media(
        "proj-B", [synthetic_jpeg, synthetic_png]
    )
    hashes = {r.content_hash for r in records}
    assert len(hashes) == 2

    async with connection() as db:
        cursor = await db.execute(
            "SELECT content_hash FROM project_media WHERE project_id = ?",
            ("proj-B",),
        )
        rows = await cursor.fetchall()
    assert {row["content_hash"] for row in rows} == hashes


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_skips_unknown_extension(tmp_path: Path) -> None:
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello")
    records = await stage1_ingest.ingest_media("proj-A", [bogus])
    assert records == []


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_skips_missing_path(tmp_path: Path) -> None:
    records = await stage1_ingest.ingest_media("proj-A", [tmp_path / "nope.jpg"])
    assert records == []


# ---- Video ingest ------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_video_extracts_scenes_and_frames(
    synthetic_video: Path,
) -> None:
    records = await stage1_ingest.ingest_media("proj-V", [synthetic_video])
    assert len(records) == 1
    rec = records[0]
    assert rec.media_type == "video"
    assert rec.quick_stats["width"] == 320
    assert rec.quick_stats["height"] == 240
    assert rec.quick_stats["fps"] > 0
    assert rec.quick_stats["scene_count"] >= 1
    assert rec.scenes is not None
    for scene in rec.scenes:
        # Each scene should have produced at least one representative frame.
        assert len(scene.representative_frame_paths) >= 1
        for fp in scene.representative_frame_paths:
            assert Path(fp).is_file()

    scenes_json = (
        paths_mod.projects_dir()
        / "proj-V"
        / "cache"
        / "scenes"
        / rec.content_hash
        / "scenes.json"
    )
    assert scenes_json.is_file()
    parsed = json.loads(scenes_json.read_text(encoding="utf-8"))
    assert len(parsed) == len(rec.scenes)


@pytest.mark.usefixtures("db_initialized")
async def test_ingest_respects_scene_cap(synthetic_video: Path) -> None:
    records = await stage1_ingest.ingest_media(
        "proj-V", [synthetic_video], scene_cap=1
    )
    assert records[0].scenes is not None
    assert len(records[0].scenes) <= 1
