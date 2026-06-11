"""Stage 6 music-video tests — clip durations snap to the cut grid."""

from __future__ import annotations

import pytest

from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.media.music import CutGrid, MusicAnalysis
from impact_crater.pipeline import stage6_plan
from impact_crater.pipeline.stage1_ingest import MediaRecord
from impact_crater.pipeline.stage6_plan import StandardMusicSpec, compile_plan
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()


def _photo(content_hash: str) -> MediaRecord:
    return MediaRecord(
        content_hash=content_hash,
        source_path=f"/tmp/{content_hash}.jpg",
        media_type="photo",
        file_size=1024,
        quick_stats={"width": 1920, "height": 1080, "phash": "00", "dhash": "00"},
    )


def _arc(items: list[SelectedItem]) -> ArcJudgment:
    return ArcJudgment(selected_items=items, arc_reasoning="t", confidence=0.7)


def _music(cut_points_ms: list[int], duration_ms: int = 8000) -> StandardMusicSpec:
    grid = CutGrid(
        cut_points_ms=cut_points_ms,
        section_aligned_cuts=[],
        cut_frequency_beats=4,
        bpm=120.0,
    )
    analysis = MusicAnalysis(
        duration_ms=duration_ms,
        bpm=120.0,
        bpm_stability=0.95,
        beats_ms=list(range(0, duration_ms, 500)),
        downbeats_ms=list(range(0, duration_ms, 2000)),
        sections=[],
        energy_curve=[],
        spectral_novelty=[],
        analyzer="test",
    )
    return StandardMusicSpec(
        audio_path="/tmp/song.wav",
        audio_duration_ms=duration_ms,
        music_analysis=analysis,
        cut_grid=grid,
    )


# ---- Tests -------------------------------------------------------------


@pytest.mark.usefixtures("db_initialized")
async def test_clip_boundaries_snap_to_cut_points_and_cover_target() -> None:
    """Three equally-paced clips over an 8s target: every transition must
    land on a grid cut and the timeline must run the full target."""
    photos = [_photo(f"h-{i}") for i in range(3)]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref=f"h-{i}",
                placement_position=i,
                intended_duration_ms=2667,  # ~8s / 3
                role="r",
            )
            for i in range(3)
        ]
    )
    music = _music([0, 2000, 3000, 5000, 6000, 8000])
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="p-mv",
        target_duration_seconds=8,
        mode="music_video",
        audio=music,
    )
    assert plan.mode == "music_video"
    assert len(plan.clips) == 3
    durations = [c.intended_duration_ms for c in plan.clips]
    assert sum(durations) == 8000  # covers the target, no silent tail
    # Interior boundaries (cumulative ends of clips 0..n-2) land on cuts.
    boundaries = [sum(durations[: i + 1]) for i in range(len(durations) - 1)]
    assert all(b in {0, 2000, 3000, 5000, 6000, 8000} for b in boundaries)


@pytest.mark.usefixtures("db_initialized")
async def test_all_clips_kept_and_timeline_fills_target() -> None:
    """Regression: 5 clips × 1s against a sparse 2-cut grid used to keep
    only 2 clips and end the video at 4s of a 5s job. All clips must
    survive and the timeline must cover the target."""
    photos = [_photo(f"h-{i}") for i in range(5)]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref=f"h-{i}",
                placement_position=i,
                intended_duration_ms=1000,
                role="r",
            )
            for i in range(5)
        ]
    )
    music = _music([0, 2000, 4000], duration_ms=8000)
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="p-mv-tail",
        target_duration_seconds=5,
        mode="music_video",
        audio=music,
    )
    assert len(plan.clips) == 5
    assert [c.candidate_ref for c in plan.clips] == [f"h-{i}" for i in range(5)]
    total = sum(c.intended_duration_ms for c in plan.clips)
    assert total == 5000
    # Every clip respects the 250ms floor.
    assert all(c.intended_duration_ms >= 250 for c in plan.clips)


@pytest.mark.usefixtures("db_initialized")
async def test_degenerate_grid_falls_back_to_linear_scale() -> None:
    """Single cut point can't produce intervals; runner falls back to scale_to_target."""
    photos = [_photo(f"h-{i}") for i in range(2)]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref=f"h-{i}",
                placement_position=i,
                intended_duration_ms=2000,
                role="r",
            )
            for i in range(2)
        ]
    )
    # Cut grid with only one point (above the target_ms) → treated as degenerate.
    music = _music([10_000])
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="p-mv-degen",
        target_duration_seconds=4,
        mode="music_video",
        audio=music,
    )
    # Degenerate grid → linear scale fallback (sum within ±10% of 4000).
    total = sum(c.intended_duration_ms for c in plan.clips)
    assert 3600 <= total <= 4400


@pytest.mark.usefixtures("db_initialized")
async def test_music_video_mode_persists_music_spec_with_grid() -> None:
    photos = [_photo("h-mv")]
    arc = _arc(
        [
            SelectedItem(
                candidate_ref="h-mv",
                placement_position=0,
                intended_duration_ms=1000,
                role="opener",
            )
        ]
    )
    music = _music([0, 2000, 4000])
    plan = await compile_plan(
        arc_judgment=arc,
        ingest_records=photos,
        project_id="p-mv-persist",
        target_duration_seconds=4,
        mode="music_video",
        audio=music,
    )
    loaded = stage6_plan.load_plan(plan.snapshot_id, "p-mv-persist")
    assert loaded.mode == "music_video"
    assert loaded.music is not None
    assert loaded.music.cut_grid is not None
    assert loaded.music.cut_grid.cut_points_ms == [0, 2000, 4000]
