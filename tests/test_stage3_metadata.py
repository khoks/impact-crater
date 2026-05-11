"""Stage 3 rich-metadata tests with mocked router.

The router stub returns dicts that pass / fail D-009 schema validation;
Stage 3 wraps them in Pydantic models or raises LLMOperationFailed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from impact_crater.llm_clients.exceptions import LLMOperationFailed
from impact_crater.pipeline import stage3_metadata
from impact_crater.pipeline.stage1_ingest import MediaRecord, SceneRecord
from impact_crater.pipeline.types import RichMetadataPhoto, RichMetadataVideoScene


def _photo_record(tmp_path: Path, content_hash: str = "h-photo") -> MediaRecord:
    img = Image.new("RGB", (320, 240), (10, 200, 50))
    p = tmp_path / f"{content_hash}.jpg"
    img.save(p, format="JPEG", quality=80)
    return MediaRecord(
        content_hash=content_hash,
        source_path=str(p),
        media_type="photo",
        file_size=p.stat().st_size,
        quick_stats={"width": 320, "height": 240},
    )


def _video_record(tmp_path: Path) -> MediaRecord:
    scene_dir = tmp_path / "scene_frames"
    scene_dir.mkdir()
    frames = []
    for label in ("start", "middle", "end"):
        f = scene_dir / f"scene-0-{label}.png"
        Image.new("RGB", (200, 200), (180, 80, 30)).save(f, "PNG")
        frames.append(str(f))
    src = tmp_path / "video.mp4"
    src.write_bytes(b"fake-video")
    return MediaRecord(
        content_hash="h-video",
        source_path=str(src),
        media_type="video",
        file_size=src.stat().st_size,
        quick_stats={"scene_count": 1},
        scenes=[
            SceneRecord(
                index=0,
                start_seconds=0.0,
                end_seconds=2.0,
                representative_frame_paths=frames,
            )
        ],
    )


def _valid_photo_metadata() -> dict:
    return {
        "time_of_day": "midday",
        "people": {"count": 2, "in_focus": ["adult woman center", "child left"]},
        "location": {"description": "alpine meadow", "lat_long": None},
        "mood": "calm",
        "lighting": "soft overcast",
        "quality": 0.78,
        "foreground_activity": "two people walking",
        "background_activity": "wind moving grass",
        "objects": ["S:phone", "M:backpack"],
        "clothing": ["red jacket", "blue beanie"],
        "pose_quality_scores": None,
        "generic_tags": ["alpine", "meadow", "two-people"],
        "task_context_tags": ["family-trip"],
        "recognized_persons": [],
    }


async def test_stage3_validates_photo_metadata(tmp_path: Path) -> None:
    router = AsyncMock()
    router.extract_metadata_image = AsyncMock(return_value=_valid_photo_metadata())

    out = await stage3_metadata.run_stage3(
        router=router,
        media=[_photo_record(tmp_path)],
        brief="alpine family trip",
    )
    assert len(out) == 1
    assert out[0].content_hash == "h-photo"
    assert isinstance(out[0].metadata, RichMetadataPhoto)
    assert out[0].metadata.time_of_day == "midday"
    assert out[0].metadata.people.count == 2
    assert out[0].metadata.quality == pytest.approx(0.78)


async def test_stage3_validates_video_scene_metadata(tmp_path: Path) -> None:
    router = AsyncMock()
    payload = _valid_photo_metadata() | {"scene_summary": "two people walking through meadow"}
    router.extract_metadata_image = AsyncMock(return_value=payload)

    out = await stage3_metadata.run_stage3(
        router=router,
        media=[_video_record(tmp_path)],
        brief="b",
    )
    assert len(out) == 1
    assert out[0].scene_index == 0
    assert isinstance(out[0].metadata, RichMetadataVideoScene)
    assert out[0].metadata.scene_summary.startswith("two people walking")


async def test_stage3_propagates_brief_via_prompt_vars(tmp_path: Path) -> None:
    router = AsyncMock()
    router.extract_metadata_image = AsyncMock(return_value=_valid_photo_metadata())

    await stage3_metadata.run_stage3(
        router=router,
        media=[_photo_record(tmp_path)],
        brief="vacation in italy",
    )
    call = router.extract_metadata_image.await_args
    assert call.kwargs["prompt_vars"]["context_brief"] == "vacation in italy"


async def test_stage3_raises_when_every_asset_fails_schema(tmp_path: Path) -> None:
    """Per-asset failures are now tolerated (the asset is skipped + logged
    as WARN); but if EVERY asset fails the stage raises so we don't
    silently produce a degraded job. Single-asset input here = 100% rate."""
    router = AsyncMock()
    # `quality` out of [0,1] range — Pydantic ValidationError → LLMOperationFailed.
    bad = _valid_photo_metadata() | {"quality": 1.7}
    router.extract_metadata_image = AsyncMock(return_value=bad)

    with pytest.raises(RuntimeError) as excinfo:
        await stage3_metadata.run_stage3(
            router=router,
            media=[_photo_record(tmp_path)],
            brief="b",
        )
    assert "every asset failed" in str(excinfo.value)


async def test_stage3_skips_failing_asset_and_returns_partial_results(tmp_path: Path) -> None:
    """One bad asset out of three should NOT kill the batch — the surviving
    two are returned and the failure is logged. Real failure motivating
    this: one bad image killed a 545-asset Stage 3.

    Stage 3 dispatches via `pool.submit_many_tolerant` which awaits all
    items concurrently via asyncio.gather. The order in which the mock's
    side_effect runs is therefore NOT deterministic, so we route by
    content_hash (the kwarg the router passes through) rather than by
    iteration order — that way the bad payload always lands on the same
    asset regardless of scheduling."""
    router = AsyncMock()
    good = _valid_photo_metadata()
    bad = _valid_photo_metadata() | {"quality": 1.7}  # ValidationError on bad

    async def _by_hash(*args: object, content_hash: str = "", **kwargs: object) -> dict:
        return bad if content_hash == "h1" else good

    router.extract_metadata_image = AsyncMock(side_effect=_by_hash)

    media = []
    for i in range(3):
        p = tmp_path / f"p{i}"
        p.mkdir()
        media.append(_photo_record(p, content_hash=f"h{i}"))

    out = await stage3_metadata.run_stage3(router=router, media=media, brief="b")
    # Two of three survive — h1 is skipped silently in the result.
    assert len(out) == 2
    assert {a.content_hash for a in out} == {"h0", "h2"}


async def test_stage3_handles_multiple_photos(tmp_path: Path) -> None:
    router = AsyncMock()
    router.extract_metadata_image = AsyncMock(return_value=_valid_photo_metadata())

    media = []
    for i in range(3):
        p = tmp_path / f"p{i}"
        p.mkdir()
        media.append(_photo_record(p, content_hash=f"h{i}"))
    out = await stage3_metadata.run_stage3(router=router, media=media, brief="b")
    assert len(out) == 3
    assert {a.content_hash for a in out} == {"h0", "h1", "h2"}
    assert router.extract_metadata_image.await_count == 3
