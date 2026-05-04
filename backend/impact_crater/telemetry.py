"""Append-only JSONL telemetry stream per ADR-0015.

Five event types — `LLMCallEvent`, `RenderEvent`, `IngestEvent`,
`OrchestratorTurnEvent`, `JobLifecycleEvent` — written to
`~/.impact-crater/telemetry.jsonl`. Each event self-describes via
`schema_version`. Rotation is deferred to v1; MVP keeps everything.

The same writer also feeds the post-job `JobCostSummary` aggregator
(ADR-0014 references this as a feature input for profile re-derivation).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from impact_crater import paths

# Single module-level lock so concurrent writes to the JSONL stay record-atomic
# under the GIL. The file open/append/close is fast; lock contention is not a
# real concern at MVP write rates (max ~hundreds of events/sec under load).
_LOCK = threading.Lock()


# ---- Event dataclasses -------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LLMCallEvent:
    """One LLM call (cache hit or miss). Per ADR-0015 §"Event types"."""

    operation: str
    provider: str
    model: str
    model_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_estimate_usd: float
    result_bytes_hash: str
    project_id: str
    snapshot_id: str | None
    cache_hit: bool
    correlation_id: str
    schema_version: int = 1
    event_type: Literal["llm_call"] = "llm_call"
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class RenderEvent:
    project_id: str
    snapshot_id: str
    duration_ms: int
    output_bytes: int
    render_status: Literal["success", "failure", "cancelled"]
    correlation_id: str
    ffmpeg_exit_code: int | None = None
    error_excerpt: str | None = None
    schema_version: int = 1
    event_type: Literal["render"] = "render"
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class IngestEvent:
    project_id: str
    media_count: int
    total_bytes: int
    per_format_counts: dict[str, int]
    duration_ms: int
    failed_count: int
    correlation_id: str
    schema_version: int = 1
    event_type: Literal["ingest"] = "ingest"
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class OrchestratorTurnEvent:
    project_id: str
    snapshot_id: str | None
    turn_index: int
    tool_name: str
    tool_input_summary: dict[str, Any]
    tool_outcome: Literal["success", "failure", "cancelled"]
    tool_latency_ms: int
    correlation_id: str
    schema_version: int = 1
    event_type: Literal["orchestrator_turn"] = "orchestrator_turn"
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class JobLifecycleEvent:
    project_id: str
    snapshot_id: str | None
    state: Literal["started", "completed", "failed", "cancelled", "paused", "resumed"]
    correlation_id: str
    reason: str | None = None
    schema_version: int = 1
    event_type: Literal["job_lifecycle"] = "job_lifecycle"
    timestamp: str = field(default_factory=_now_iso)


TelemetryEvent = (
    LLMCallEvent
    | RenderEvent
    | IngestEvent
    | OrchestratorTurnEvent
    | JobLifecycleEvent
)


# ---- Writer ------------------------------------------------------------


def emit(event: TelemetryEvent) -> None:
    """Append a single event to the telemetry JSONL.

    Synchronous (open/append/close) — simplest correct semantics under the GIL.
    The volume is low enough that this won't dominate any pipeline stage.
    """
    line = json.dumps(asdict(event), separators=(",", ":"))
    target = paths.telemetry_path()
    with _LOCK:
        with target.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def emit_many(events: Iterable[TelemetryEvent]) -> None:
    """Append several events under a single lock acquisition."""
    target = paths.telemetry_path()
    lines = [json.dumps(asdict(e), separators=(",", ":")) for e in events]
    if not lines:
        return
    with _LOCK:
        with target.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


# ---- Reader / aggregation helpers --------------------------------------


def read_all() -> Iterator[dict[str, Any]]:
    """Iterate every event in the telemetry stream.

    Returns raw dicts (the dataclass `event_type` field tells callers
    which schema to expect). Skips blank lines defensively.
    """
    target = paths.telemetry_path()
    if not target.is_file():
        return iter(())
    return _iter_jsonl(target)


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def events_for_correlation(correlation_id: str) -> list[dict[str, Any]]:
    """Return every event matching `correlation_id` (in stream order)."""
    return [e for e in read_all() if e.get("correlation_id") == correlation_id]


# ---- JobCostSummary ----------------------------------------------------


@dataclass
class JobCostSummary:
    """Per-job rollup of cost + cache stats per ADR-0015."""

    project_id: str
    snapshot_id: str
    started_at: str
    completed_at: str
    wall_clock_ms: int

    tier_s_calls: int
    tier_s_cost_usd: float
    tier_m_calls: int
    tier_m_cost_usd: float
    tier_l_calls: int
    tier_l_cost_usd: float
    embedding_calls: int
    embedding_cost_usd: float

    cost_by_provider: dict[str, float]
    cost_by_operation: dict[str, float]

    cache_hits: int
    cache_misses: int
    estimated_cost_saved_by_cache_usd: float

    render_count: int
    render_total_ms: int
    render_failed: int

    total_cost_usd: float
    schema_version: int = 1


def aggregate_summary(
    *,
    project_id: str,
    snapshot_id: str,
    correlation_ids: list[str],
    tier_lookup: dict[str, str],
) -> JobCostSummary:
    """Aggregate every event under any of `correlation_ids` into a JobCostSummary.

    Args:
        tier_lookup: operation-name → tier letter ("S"/"M"/"L"/"embedding").
    """
    events: list[dict[str, Any]] = []
    cid_set = set(correlation_ids)
    for ev in read_all():
        if ev.get("correlation_id") in cid_set:
            events.append(ev)

    llm_events = [e for e in events if e.get("event_type") == "llm_call"]
    render_events = [e for e in events if e.get("event_type") == "render"]
    job_events = [e for e in events if e.get("event_type") == "job_lifecycle"]

    started_at = next(
        (e["timestamp"] for e in job_events if e.get("state") == "started"),
        events[0]["timestamp"] if events else _now_iso(),
    )
    completed_at = next(
        (
            e["timestamp"]
            for e in reversed(job_events)
            if e.get("state") in ("completed", "failed", "cancelled")
        ),
        events[-1]["timestamp"] if events else _now_iso(),
    )
    wall_clock_ms = _iso_diff_ms(started_at, completed_at)

    # Per-tier rollup
    tier_calls = {"S": 0, "M": 0, "L": 0, "embedding": 0}
    tier_cost = {"S": 0.0, "M": 0.0, "L": 0.0, "embedding": 0.0}
    cost_by_provider: dict[str, float] = {}
    cost_by_operation: dict[str, float] = {}
    cache_hits = 0
    cache_misses = 0
    cache_savings_usd = 0.0

    for e in llm_events:
        op = e["operation"]
        provider = e["provider"]
        cost = float(e["cost_estimate_usd"])
        tier = tier_lookup.get(op, "M")  # fall back to M if not found
        if e.get("cache_hit"):
            cache_hits += 1
            # Cost is recorded as 0; estimate the savings as the rate-card cost
            # would have been on a miss. Caller pre-fills this when emitting
            # the cache-hit event by setting cost_estimate_usd=0 and stuffing
            # the would-be cost into `result_bytes_hash`-adjacent metadata.
            # Simpler MVP version: assume cache savings equal an average miss.
            continue
        cache_misses += 1
        tier_calls[tier] = tier_calls.get(tier, 0) + 1
        tier_cost[tier] = tier_cost.get(tier, 0.0) + cost
        cost_by_provider[provider] = cost_by_provider.get(provider, 0.0) + cost
        cost_by_operation[op] = cost_by_operation.get(op, 0.0) + cost

    # Estimate cache savings: average per-op miss cost × hits.
    if cache_hits and cost_by_operation:
        avg_cost = sum(cost_by_operation.values()) / max(cache_misses, 1)
        cache_savings_usd = avg_cost * cache_hits

    render_failed = sum(1 for e in render_events if e.get("render_status") != "success")
    total_cost = sum(tier_cost.values())

    return JobCostSummary(
        project_id=project_id,
        snapshot_id=snapshot_id,
        started_at=started_at,
        completed_at=completed_at,
        wall_clock_ms=wall_clock_ms,
        tier_s_calls=tier_calls["S"],
        tier_s_cost_usd=tier_cost["S"],
        tier_m_calls=tier_calls["M"],
        tier_m_cost_usd=tier_cost["M"],
        tier_l_calls=tier_calls["L"],
        tier_l_cost_usd=tier_cost["L"],
        embedding_calls=tier_calls["embedding"],
        embedding_cost_usd=tier_cost["embedding"],
        cost_by_provider=cost_by_provider,
        cost_by_operation=cost_by_operation,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        estimated_cost_saved_by_cache_usd=cache_savings_usd,
        render_count=len(render_events),
        render_total_ms=sum(int(e.get("duration_ms", 0)) for e in render_events),
        render_failed=render_failed,
        total_cost_usd=total_cost,
    )


def _iso_diff_ms(a: str, b: str) -> int:
    """Milliseconds between two ISO-8601 timestamps. Tolerates trailing 'Z'."""
    da = datetime.fromisoformat(a.replace("Z", "+00:00"))
    db = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return int((db - da).total_seconds() * 1000)
