"""`_run_and_capture` turns pipeline exceptions into terminal job states."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from impact_crater.jobs import runner_glue
from impact_crater.jobs.registry import JobRegistry, JobSnapshot
from impact_crater.pipeline.runner import FullJobConfig, QuotaDeniedError
from impact_crater.storage.migrations import run_pending_migrations


class _Router:
    def set_progress_sink(self, sink: Any) -> None:
        self.sink = sink


async def test_quota_denied_job_fails_with_the_quota_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def _deny(*_args: Any, **_kwargs: Any) -> None:
        raise QuotaDeniedError("daily_cap_reached", {"estimate_usd": 1.5})

    monkeypatch.setattr(runner_glue, "run_full_pipeline", _deny)
    await run_pending_migrations()
    registry = JobRegistry()
    await registry.register(JobSnapshot(job_id="j1", project_id="p1"))
    config = FullJobConfig(
        media_paths=[],
        brief="b",
        target_duration_seconds=30,
        audio_path=tmp_path / "a.mp3",
    )

    await runner_glue._run_and_capture(
        config,
        _Router(),  # type: ignore[arg-type]
        runner_glue._RegistryReporter(registry, "j1"),
        registry,
        "j1",
    )

    snap = registry.get("j1")
    assert snap is not None
    assert snap.state == "failed"
    assert snap.failure_reason == "quota_denied:daily_cap_reached"
