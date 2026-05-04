"""Unit tests for the telemetry stream + JobCostSummary aggregator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impact_crater import telemetry


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_emit_writes_one_line(isolated_home: Path) -> None:
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="caption_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
            input_tokens=120,
            output_tokens=8,
            latency_ms=540,
            cost_estimate_usd=0.001,
            result_bytes_hash="abc",
            project_id="proj1",
            snapshot_id=None,
            cache_hit=False,
            correlation_id="cid1",
        )
    )
    rows = _read_lines(isolated_home / "telemetry.jsonl")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "llm_call"
    assert rows[0]["operation"] == "caption_image"
    assert rows[0]["schema_version"] == 1


def test_emit_many_writes_in_order(isolated_home: Path) -> None:
    events = [
        telemetry.JobLifecycleEvent(
            project_id="p", snapshot_id="s", state="started", correlation_id="c"
        ),
        telemetry.IngestEvent(
            project_id="p",
            media_count=10,
            total_bytes=1024,
            per_format_counts={"jpeg": 10},
            duration_ms=200,
            failed_count=0,
            correlation_id="c",
        ),
        telemetry.JobLifecycleEvent(
            project_id="p", snapshot_id="s", state="completed", correlation_id="c"
        ),
    ]
    telemetry.emit_many(events)
    rows = _read_lines(isolated_home / "telemetry.jsonl")
    assert [r["event_type"] for r in rows] == [
        "job_lifecycle",
        "ingest",
        "job_lifecycle",
    ]


def test_events_for_correlation_filters(isolated_home: Path) -> None:
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="op",
            provider="anthropic",
            model="m",
            model_version="v",
            input_tokens=0,
            output_tokens=0,
            latency_ms=1,
            cost_estimate_usd=0.0,
            result_bytes_hash="",
            project_id="p",
            snapshot_id=None,
            cache_hit=False,
            correlation_id="cid-A",
        )
    )
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="op",
            provider="anthropic",
            model="m",
            model_version="v",
            input_tokens=0,
            output_tokens=0,
            latency_ms=1,
            cost_estimate_usd=0.0,
            result_bytes_hash="",
            project_id="p",
            snapshot_id=None,
            cache_hit=False,
            correlation_id="cid-B",
        )
    )
    a = telemetry.events_for_correlation("cid-A")
    b = telemetry.events_for_correlation("cid-B")
    assert len(a) == 1 and a[0]["correlation_id"] == "cid-A"
    assert len(b) == 1 and b[0]["correlation_id"] == "cid-B"


def test_aggregate_summary_buckets_by_tier(isolated_home: Path) -> None:
    cid = "job-X"
    telemetry.emit(
        telemetry.JobLifecycleEvent(
            project_id="p", snapshot_id="s", state="started", correlation_id=cid
        )
    )
    # Tier-S call (Flash caption)
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="caption_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
            input_tokens=200,
            output_tokens=10,
            latency_ms=400,
            cost_estimate_usd=0.001,
            result_bytes_hash="h1",
            project_id="p",
            snapshot_id="s",
            cache_hit=False,
            correlation_id=cid,
        )
    )
    # Tier-M call (Sonnet metadata)
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="extract_metadata_image",
            provider="anthropic",
            model="claude-sonnet-4-5",
            model_version="latest",
            input_tokens=400,
            output_tokens=120,
            latency_ms=900,
            cost_estimate_usd=0.005,
            result_bytes_hash="h2",
            project_id="p",
            snapshot_id="s",
            cache_hit=False,
            correlation_id=cid,
        )
    )
    # Tier-L call (Opus judge)
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="judge_narrative_arc",
            provider="anthropic",
            model="claude-opus-4-5",
            model_version="latest",
            input_tokens=2000,
            output_tokens=500,
            latency_ms=4000,
            cost_estimate_usd=0.50,
            result_bytes_hash="h3",
            project_id="p",
            snapshot_id="s",
            cache_hit=False,
            correlation_id=cid,
        )
    )
    # Cache hit (cost $0)
    telemetry.emit(
        telemetry.LLMCallEvent(
            operation="caption_image",
            provider="google",
            model="gemini-2.5-flash",
            model_version="v1",
            input_tokens=0,
            output_tokens=0,
            latency_ms=2,
            cost_estimate_usd=0.0,
            result_bytes_hash="h1",
            project_id="p",
            snapshot_id="s",
            cache_hit=True,
            correlation_id=cid,
        )
    )
    telemetry.emit(
        telemetry.RenderEvent(
            project_id="p",
            snapshot_id="s",
            duration_ms=12000,
            output_bytes=8_000_000,
            render_status="success",
            correlation_id=cid,
        )
    )
    telemetry.emit(
        telemetry.JobLifecycleEvent(
            project_id="p", snapshot_id="s", state="completed", correlation_id=cid
        )
    )

    tier_lookup = {
        "caption_image": "S",
        "extract_metadata_image": "M",
        "judge_narrative_arc": "L",
    }
    summary = telemetry.aggregate_summary(
        project_id="p", snapshot_id="s", correlation_ids=[cid], tier_lookup=tier_lookup
    )
    assert summary.tier_s_calls == 1
    assert summary.tier_m_calls == 1
    assert summary.tier_l_calls == 1
    assert summary.tier_s_cost_usd == pytest.approx(0.001)
    assert summary.tier_m_cost_usd == pytest.approx(0.005)
    assert summary.tier_l_cost_usd == pytest.approx(0.50)
    assert summary.cache_hits == 1
    assert summary.cache_misses == 3
    assert summary.cost_by_provider["google"] == pytest.approx(0.001)
    assert summary.cost_by_provider["anthropic"] == pytest.approx(0.505)
    assert summary.render_count == 1
    assert summary.render_failed == 0
    assert summary.total_cost_usd == pytest.approx(0.506)


def test_read_all_returns_empty_when_file_missing(isolated_home: Path) -> None:
    assert list(telemetry.read_all()) == []
