"""Stage 6 plan-compile tests — clip resolution, duration scaling, persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from impact_crater import paths
from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.pipeline import stage6_plan
from impact_crater.pipeline.stage1_ingest import MediaRecord, SceneRecord
from impact_crater.pipeline.stage6_plan import (
    RenderClip,
    StandardMusicSpec,
    compile_plan,
    load_plan,
)
from impact_crater.storage.db import connection
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


def _photo_record(content_hash: str, *, width: int = 1920, height: int = 1080) -> MediaRecord:
    return MediaRecord(
        content_hash=content_hash,
        source_path=f"/tmp/{content_hash}.jpg",
        media_type="photo",
        file_size=1024,
        quick_stats={"width": width, "height": height, "phash": "00", "dhash": "00"},
    )


def _video_record(
    content_hash: str,
    *,
    scenes: list[SceneRecord],
    width: int = 1920,
    height: int = 1080,
) -> MediaRecord:
    return MediaRecord(
        content_hash=content_hash,
        source_path=f"/tmp/{content_hash}.mp4",
        media_type="video",
        file_size=4096,
        quick_stats={"width": width, "height": height, "fps": 24.0, "duration_seconds": 4.0},
        scenes=scenes,
    )


def _arc(items: list[SelectedItem], *, confidence: float = 0.7, reasoning: str = "test") -> ArcJudgment:
    return ArcJudgment(selected_items=items, arc_reasoning=reasoning, confidence=confidence)


# ---- Resolution + clip kinds ------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_compile_resolves_photo_and_video_scene_refs() -> None:
    photo = _photo_record("h-photo")
    video = _video_record(
        "h-video",
        scenes=[
            SceneRecord(
                index=0,
                start_seconds=0.0,
                end_seconds=2.0,
                representative_frame_paths=["/tmp/f0.png", "/tmp/f1.png", "/tmp/f2.png"],
            )
        ],
    )
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-photo",
                placement_position=0,
                intended_duration_ms=2000,
                role="opener",
            ),
            SelectedItem(
                candidate_ref="h-video#0",
                placement_position=1,
                intended_duration_ms=1500,
                role="peak",
            ),
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo, video],
        project_id="proj-1",
        target_duration_seconds=4,
    )
    assert len(plan.clips) == 2
    assert plan.clips[0].kind == "photo"
    assert plan.clips[0].source_path == "/tmp/h-photo.jpg"
    assert plan.clips[1].kind == "video_scene"
    assert plan.clips[1].start_seconds == 0.0
    assert plan.clips[1].end_seconds == 2.0


@pytest.mark.usefixtures("db_initialized")
async def test_compile_skips_unknown_refs() -> None:
    photo = _photo_record("h-known")
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-known",
                placement_position=0,
                intended_duration_ms=2000,
                role="opener",
            ),
            SelectedItem(
                candidate_ref="h-missing",
                placement_position=1,
                intended_duration_ms=2000,
                role="closer",
            ),
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo],
        project_id="proj-skip",
        target_duration_seconds=4,
    )
    assert len(plan.clips) == 1
    assert plan.clips[0].candidate_ref == "h-known"


@pytest.mark.usefixtures("db_initialized")
async def test_compile_orders_by_placement_position() -> None:
    photos = [_photo_record(f"h-{i}") for i in range(3)]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-2",
                placement_position=2,
                intended_duration_ms=1000,
                role="closer",
            ),
            SelectedItem(
                candidate_ref="h-0",
                placement_position=0,
                intended_duration_ms=1000,
                role="opener",
            ),
            SelectedItem(
                candidate_ref="h-1",
                placement_position=1,
                intended_duration_ms=1000,
                role="peak",
            ),
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="proj-order",
        target_duration_seconds=3,
    )
    assert [c.candidate_ref for c in plan.clips] == ["h-0", "h-1", "h-2"]


# ---- Aspect-ratio action picker ---------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_landscape_photo_uses_as_is() -> None:
    photo = _photo_record("h-landscape", width=1920, height=1080)
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-landscape",
                placement_position=0,
                intended_duration_ms=1500,
                role="opener",
            )
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo],
        project_id="p-land",
        target_duration_seconds=2,
    )
    assert plan.clips[0].aspect_ratio_action == "as_is"


@pytest.mark.usefixtures("db_initialized")
async def test_portrait_photo_smart_crops() -> None:
    photo = _photo_record("h-portrait", width=1080, height=1920)
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-portrait",
                placement_position=0,
                intended_duration_ms=1500,
                role="opener",
            )
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo],
        project_id="p-port",
        target_duration_seconds=2,
    )
    assert plan.clips[0].aspect_ratio_action == "smart_crop"


@pytest.mark.usefixtures("db_initialized")
async def test_portrait_video_letterboxes() -> None:
    video = _video_record(
        "h-vert",
        width=1080,
        height=1920,
        scenes=[
            SceneRecord(
                index=0,
                start_seconds=0.0,
                end_seconds=2.0,
                representative_frame_paths=["/tmp/f.png"],
            )
        ],
    )
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-vert#0",
                placement_position=0,
                intended_duration_ms=1500,
                role="opener",
            )
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[video],
        project_id="p-vert",
        target_duration_seconds=2,
    )
    assert plan.clips[0].aspect_ratio_action == "letterbox"


# ---- Duration scaling --------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_clip_durations_scale_to_target_within_tolerance() -> None:
    """Photos: 3 clips × 5000ms = 15000ms total; target 5000ms → scale by 1/3."""
    photos = [_photo_record(f"h-{i}") for i in range(3)]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref=f"h-{i}",
                placement_position=i,
                intended_duration_ms=5000,
                role="filler",
            )
            for i in range(3)
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="p-scale",
        target_duration_seconds=5,
    )
    total_ms = sum(c.intended_duration_ms for c in plan.clips)
    # Within ±10% of 5000ms.
    assert 4500 <= total_ms <= 5500


@pytest.mark.usefixtures("db_initialized")
async def test_within_tolerance_no_scaling() -> None:
    """If sum is already within ±10%, leave durations alone."""
    photos = [_photo_record(f"h-{i}") for i in range(2)]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-0",
                placement_position=0,
                intended_duration_ms=2400,
                role="o",
            ),
            SelectedItem(
                candidate_ref="h-1",
                placement_position=1,
                intended_duration_ms=2400,
                role="c",
            ),
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="p-tol",
        target_duration_seconds=5,
    )
    total_ms = sum(c.intended_duration_ms for c in plan.clips)
    assert total_ms == 4800  # untouched, within ±10% of 5000


# ---- Persistence -------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_compile_writes_plan_json_and_db_row() -> None:
    photo = _photo_record("h-persist")
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-persist",
                placement_position=0,
                intended_duration_ms=2000,
                role="opener",
            )
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo],
        project_id="p-fs",
        target_duration_seconds=2,
    )
    plan_file = (
        paths.projects_dir()
        / "p-fs"
        / "snapshots"
        / plan.snapshot_id
        / "plan.json"
    )
    assert plan_file.is_file()

    async with connection() as db:
        cursor = await db.execute(
            "SELECT id, project_id, plan_path, render_status FROM snapshots WHERE id = ?",
            (plan.snapshot_id,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row["project_id"] == "p-fs"
    assert row["render_status"] == "pending"
    assert row["plan_path"] == str(plan_file)


@pytest.mark.usefixtures("db_initialized")
async def test_load_plan_round_trips() -> None:
    photo = _photo_record("h-rt")
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-rt",
                placement_position=0,
                intended_duration_ms=2000,
                role="opener",
            )
        ]
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo],
        project_id="p-rt",
        target_duration_seconds=2,
    )
    loaded = load_plan(plan.snapshot_id, "p-rt")
    assert loaded.snapshot_id == plan.snapshot_id
    assert loaded.clips[0].candidate_ref == "h-rt"
    assert loaded.arc_reasoning == "test"


# ---- Music spec --------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_compile_persists_music_spec() -> None:
    photo = _photo_record("h-music")
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-music",
                placement_position=0,
                intended_duration_ms=2000,
                role="opener",
            )
        ]
    )
    music = StandardMusicSpec(
        audio_path="/tmp/song.mp3",
        audio_duration_ms=180_000,
    )
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=[photo],
        project_id="p-music",
        target_duration_seconds=2,
        audio=music,
    )
    assert plan.music is not None
    assert plan.music.audio_path == "/tmp/song.mp3"
    assert plan.music.fade_in_ms == 1500


# ---- Mode validation ---------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_music_video_mode_raises_not_implemented_at_m2() -> None:
    photo = _photo_record("h-mv")
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-mv",
                placement_position=0,
                intended_duration_ms=2000,
                role="opener",
            )
        ]
    )
    with pytest.raises(NotImplementedError, match="M4"):
        await compile_plan(
            arc_judgment=arc,
            ingest_records=[photo],
            project_id="p-mv",
            target_duration_seconds=2,
            mode="music_video",
        )


@pytest.mark.usefixtures("db_initialized")
async def test_zero_resolvable_clips_raises() -> None:
    photo = _photo_record("h-other")
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-missing",
                placement_position=0,
                intended_duration_ms=2000,
                role="x",
            )
        ]
    )
    with pytest.raises(ValueError, match="zero resolvable"):
        await compile_plan(
            arc_judgment=arc,
            ingest_records=[photo],
            project_id="p-empty",
            target_duration_seconds=2,
        )
