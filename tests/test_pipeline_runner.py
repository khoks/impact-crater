"""End-to-end runner tests with mocked router.

The runner sequences Stage 1 → 2 → 3 → 4 → 5 + the dual-cap quota gate.
We mock the router to return canned responses for the LLM-touching
stages; Stages 1 and 4 run against real synthetic media so the
deterministic plumbing is genuinely exercised.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest
from PIL import Image

from impact_crater.llm_clients.base import ArcJudgment, SelectedItem
from impact_crater.pipeline.runner import (
    HeadlessJobConfig,
    QuotaDeniedError,
    run_headless_pipeline,
)
from impact_crater.pipeline.types import RichMetadataPhoto
from impact_crater.storage import settings as settings_store
from impact_crater.storage.migrations import run_pending_migrations


@pytest.fixture
async def db_initialized() -> None:
    await run_pending_migrations()
    # Set a generous spend cap so the pre-job quota check passes.
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "100.00")


def _photo(tmp_path: Path, name: str, color: tuple[int, int, int]) -> Path:
    img = Image.new("RGB", (320, 240), color)
    p = tmp_path / name
    img.save(p, format="JPEG", quality=80)
    return p


def _mock_router_for_runner() -> object:
    router = AsyncMock()
    router.caption_image = AsyncMock(return_value="A scene.")
    router.score_image = AsyncMock(side_effect=_score_by_dim)
    router.embed_image = AsyncMock(return_value=np.ones((768,), dtype=np.float32))
    router.extract_metadata_image = AsyncMock(
        return_value={
            "time_of_day": "midday",
            "people": {"count": 2, "in_focus": ["a", "b"]},
            "location": {"description": "outdoor", "lat_long": None},
            "mood": "calm",
            "lighting": "soft",
            "quality": 0.7,
            "foreground_activity": "walk",
            "background_activity": "trees",
            "objects": ["S:phone"],
            "clothing": ["jacket"],
            "pose_quality_scores": None,
            "generic_tags": ["outdoor", "trip"],
            "task_context_tags": ["family"],
            "recognized_persons": [],
        }
    )
    arc = ArcJudgment(
        selected_items=[
            SelectedItem(
                candidate_ref="hash-A",
                placement_position=0,
                intended_duration_ms=3000,
                role="opener",
            ),
        ],
        arc_reasoning="A simple opener fits the brief.",
        confidence=0.75,
        open_questions=[],
    )
    router.judge_narrative_arc = AsyncMock(return_value=arc)
    return router


async def _score_by_dim(*args, **kwargs) -> float:
    dim = kwargs.get("dimension")
    if dim == "quality":
        return 0.8
    if dim == "narrative_relevance":
        return 0.7
    return 0.5


@pytest.mark.usefixtures("db_initialized")
async def test_runner_executes_all_5_stages(tmp_path: Path) -> None:
    paths = [
        _photo(tmp_path, "p1.jpg", (200, 80, 30)),
        _photo(tmp_path, "p2.jpg", (40, 200, 100)),
        _photo(tmp_path, "p3.jpg", (60, 60, 220)),
    ]
    config = HeadlessJobConfig(
        media_paths=paths,
        brief="test brief",
        target_duration_seconds=10,
    )
    router = _mock_router_for_runner()
    result = await run_headless_pipeline(config, router=router)  # type: ignore[arg-type]

    assert result.media_count == 3
    assert result.arc_judgment.confidence == pytest.approx(0.75)
    assert result.arc_judgment.selected_items[0].role == "opener"
    assert len(result.candidate_set.items) >= 1
    assert result.quota_snapshot["allowed"] is True
    # Each stage's mock should have been awaited.
    assert router.caption_image.await_count == 3
    assert router.embed_image.await_count == 3
    assert router.extract_metadata_image.await_count == 3
    assert router.judge_narrative_arc.await_count == 1


@pytest.mark.usefixtures("db_initialized")
async def test_runner_blocks_on_quota_denial(tmp_path: Path) -> None:
    # Force the cap to a value smaller than the pre-job estimate.
    await settings_store.set_value(settings_store.KEY_TOTAL_CAP_USD, "0.10")
    paths = [_photo(tmp_path, "p.jpg", (10, 10, 10))]
    config = HeadlessJobConfig(
        media_paths=paths,
        brief="b",
        target_duration_seconds=5,
    )
    router = _mock_router_for_runner()
    with pytest.raises(QuotaDeniedError) as excinfo:
        await run_headless_pipeline(config, router=router)  # type: ignore[arg-type]
    assert excinfo.value.reason == "total_cap_would_be_exceeded"


@pytest.mark.usefixtures("db_initialized")
async def test_runner_emits_lifecycle_telemetry(tmp_path: Path) -> None:
    from impact_crater import telemetry

    paths = [_photo(tmp_path, "p1.jpg", (10, 100, 50))]
    config = HeadlessJobConfig(
        media_paths=paths,
        brief="b",
        target_duration_seconds=5,
    )
    router = _mock_router_for_runner()
    result = await run_headless_pipeline(config, router=router)  # type: ignore[arg-type]
    events = telemetry.events_for_correlation(result.correlation_id)
    states = [e.get("state") for e in events if e.get("event_type") == "job_lifecycle"]
    assert "started" in states
    assert "completed" in states


@pytest.mark.usefixtures("db_initialized")
async def test_runner_emits_failed_lifecycle_when_stage_raises(tmp_path: Path) -> None:
    from impact_crater import telemetry

    paths = [_photo(tmp_path, "p1.jpg", (10, 100, 50))]
    config = HeadlessJobConfig(
        media_paths=paths,
        brief="b",
        target_duration_seconds=5,
    )
    router = _mock_router_for_runner()
    router.judge_narrative_arc = AsyncMock(side_effect=RuntimeError("simulated"))

    with pytest.raises(RuntimeError):
        await run_headless_pipeline(config, router=router)  # type: ignore[arg-type]
    # Find the most recent correlation_id with a 'failed' lifecycle event.
    failed = [
        e
        for e in telemetry.read_all()
        if e.get("event_type") == "job_lifecycle" and e.get("state") == "failed"
    ]
    assert failed
    assert "simulated" in (failed[-1].get("reason") or "")


def test_unused_import_warning_silenced() -> None:
    """Ensure RichMetadataPhoto is still importable for downstream consumers."""
    assert RichMetadataPhoto is not None
