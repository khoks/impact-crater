"""Stage 2 bulk-ops tests with mocked router.

Real API smoke is covered by tests/integration/test_real_providers.py +
test_full_headless_pipeline.py (S-2.2.8).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest
from PIL import Image

from impact_crater.pipeline import stage1_ingest, stage2_bulk_ops
from impact_crater.pipeline.stage1_ingest import MediaRecord, SceneRecord
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


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


def _video_record(tmp_path: Path, content_hash: str = "h-video") -> MediaRecord:
    """Two-scene record where the scenes' middle frames are real PNGs on disk."""
    scene_dir = tmp_path / "scene_frames"
    scene_dir.mkdir()
    scenes = []
    for i in range(2):
        frames = []
        for label in ("start", "middle", "end"):
            f = scene_dir / f"scene-{i}-{label}.png"
            Image.new("RGB", (200, 200), (50 + i * 30, 80, 200)).save(f, "PNG")
            frames.append(str(f))
        scenes.append(
            SceneRecord(
                index=i,
                start_seconds=i * 1.0,
                end_seconds=(i + 1) * 1.0,
                representative_frame_paths=frames,
            )
        )
    src = tmp_path / "video.mp4"
    src.write_bytes(b"fake-video")
    return MediaRecord(
        content_hash=content_hash,
        source_path=str(src),
        media_type="video",
        file_size=src.stat().st_size,
        quick_stats={"scene_count": 2},
        scenes=scenes,
    )


def _mock_router() -> object:
    router = AsyncMock()
    router.caption_image = AsyncMock(return_value="A green field.")
    router.score_image = AsyncMock(side_effect=_route_score_by_dimension)
    router.embed_image = AsyncMock(return_value=np.ones((768,), dtype=np.float32))
    return router


async def _route_score_by_dimension(*args, **kwargs) -> float:
    """Quality score = 0.7; narrative-relevance = 0.4; default = 0.0."""
    dim = kwargs.get("dimension")
    if dim == "quality":
        return 0.7
    if dim == "narrative_relevance":
        return 0.4
    return 0.0


@pytest.mark.usefixtures("db_initialized")
async def test_stage2_one_photo_runs_four_ops(tmp_path: Path) -> None:
    router = _mock_router()
    out = await stage2_bulk_ops.run_stage2(
        router=router,  # type: ignore[arg-type]
        media=[_photo_record(tmp_path)],
        brief="hiking trip",
    )
    assert len(out) == 1
    asset = out[0]
    assert asset.content_hash == "h-photo"
    assert asset.scene_index is None
    assert asset.caption == "A green field."
    assert asset.quality_score == pytest.approx(0.7)
    assert asset.narrative_relevance_score == pytest.approx(0.4)
    assert asset.embedding_dim == 768


@pytest.mark.usefixtures("db_initialized")
async def test_stage2_video_emits_one_per_scene(tmp_path: Path) -> None:
    router = _mock_router()
    out = await stage2_bulk_ops.run_stage2(
        router=router,  # type: ignore[arg-type]
        media=[_video_record(tmp_path)],
        brief="any brief",
    )
    assert len(out) == 2
    indices = {a.scene_index for a in out}
    assert indices == {0, 1}
    for a in out:
        assert a.content_hash == "h-video"


@pytest.mark.usefixtures("db_initialized")
async def test_stage2_propagates_brief_to_narrative_score(tmp_path: Path) -> None:
    router = _mock_router()
    await stage2_bulk_ops.run_stage2(
        router=router,  # type: ignore[arg-type]
        media=[_photo_record(tmp_path)],
        brief="alpine summit attempt",
    )
    # Three score_image calls observed: ... actually only 2 (quality + narrative).
    score_calls = router.score_image.await_args_list
    assert len(score_calls) == 2
    narrative_call = next(c for c in score_calls if c.kwargs["dimension"] == "narrative_relevance")
    assert narrative_call.kwargs["prompt_vars"]["brief"] == "alpine summit attempt"
    # cache_extra carries the brief_hash so cache invalidates on brief change.
    assert "brief_hash" in narrative_call.kwargs["cache_extra"]


@pytest.mark.usefixtures("db_initialized")
async def test_stage2_handles_multiple_assets_in_parallel(tmp_path: Path) -> None:
    router = _mock_router()
    media = []
    for i in range(3):
        sub = tmp_path / f"asset-{i}"
        sub.mkdir()
        media.append(_photo_record(sub, content_hash=f"h{i}"))

    out = await stage2_bulk_ops.run_stage2(
        router=router,  # type: ignore[arg-type]
        media=media,
        brief="b",
    )
    assert {a.content_hash for a in out} == {"h0", "h1", "h2"}
    assert router.embed_image.await_count == 3
    assert router.caption_image.await_count == 3


def test_stage2_unused_imports_present_for_typing() -> None:
    """Smoke check that stage1_ingest types are visible (type-only import)."""
    assert stage1_ingest.MediaRecord is MediaRecord
