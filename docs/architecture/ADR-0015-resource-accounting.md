# ADR-0015 — Resource accounting + quota model

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-05-03
**Phase:** scaffolding

## Context

D-013 established **effort levels with agentic max-permissible recommendation** (L1–L3 in MVP, L4–L5 in v1). A-004 added a **per-day spend cap as MVP-lite scope** (hard stop against runaway jobs). A-015 specified the **cost-transparency UI** (running spend by provider / job / operation; agentic explanation; upgrade-path agent — last two are v1). N-006 (effort-level UX) sits over all three.

ADR-0015 formalizes:

1. The telemetry stream (events, schema, persistence).
2. Per-job rollup (`JobCostSummary` on each snapshot).
3. The rate-card configuration shape.
4. The quota model: dual-cap (total daily + per-provider daily) per Q6.
5. First-time-setup spend-cap configuration per Q5 (no system default).
6. UI surfaces (pre-job preview, in-job live spend, post-job breakdown, settings).
7. Telemetry retention + rotation policy (also serves the feedback log per ADR-0014).

Two round-3 user redirects:

- **Q5: daily spend cap = user-set during first-time setup, no system default.** The setup wizard gets a "Spend cap" step. Editable later via Settings.
- **Q6: spend cap shape = both total + per-provider caps.** A job is allowed only if it stays under both. Per-provider caps surface in the cost-breakdown UI.

## Decision

### Telemetry stream

**Append-only JSONL** at `~/.impact-crater/telemetry.jsonl`. Separate from `audit.jsonl` (publishes-only per ADR-0013) and `feedback_log.jsonl` (orchestrator profile per ADR-0014). Each event is self-describing with a `schema_version` field.

#### Event types

```python
class LLMCallEvent(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    operation: str                        # "embed_image" / "caption_image" / etc. per ADR-0007 taxonomy
    provider: str                         # "anthropic" / "google" / "local"
    model: str                            # "claude-sonnet-4-7" / "gemini-2.5-flash" / etc.
    model_version: str                    # for cache invalidation + rate-card lookup
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_estimate_usd: float              # provider-specific rate-card lookup
    result_bytes_hash: str                # for cache lookups
    project_id: str
    snapshot_id: str | None
    cache_hit: bool                       # if True, cost_estimate_usd should be 0; this is a no-op telemetry record
    correlation_id: str                   # ties multiple events from one orchestrator turn together

class RenderEvent(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    project_id: str
    snapshot_id: str
    duration_ms: int
    output_bytes: int
    render_status: Literal["success", "failure", "cancelled"]
    ffmpeg_exit_code: int | None
    error_excerpt: str | None
    correlation_id: str

class IngestEvent(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    project_id: str
    media_count: int
    total_bytes: int
    per_format_counts: dict[str, int]     # {"jpeg": 800, "heic": 150, "mp4": 50, "raw_cr2": 10}
    duration_ms: int                      # total ingest wall time
    failed_count: int
    correlation_id: str

class OrchestratorTurnEvent(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    project_id: str
    snapshot_id: str | None
    turn_index: int                       # 0..49 per session
    tool_name: str                        # which tool was selected
    tool_input_summary: dict              # truncated for telemetry
    tool_outcome: Literal["success", "failure", "cancelled"]
    tool_latency_ms: int
    correlation_id: str

class JobLifecycleEvent(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    project_id: str
    snapshot_id: str | None
    state: Literal["started", "completed", "failed", "cancelled", "paused", "resumed"]
    reason: str | None                    # e.g., "user_clicked_cancel", "max_tool_calls_exceeded"
    correlation_id: str
```

`correlation_id` ties multiple events together (one orchestrator turn → 1 OrchestratorTurnEvent + N LLMCallEvents + 0–1 RenderEvent). Used by the cost-transparency UI to attribute cost to specific orchestrator decisions.

### Per-job rollup: `JobCostSummary`

Computed at job-end (Stage 7 render-complete OR Stage 9 refinement-terminal) by aggregating all events with the job's `correlation_id` family. Persisted as `snapshots/{snapshot_id}/cost_summary.json`.

```python
class JobCostSummary(BaseModel):
    schema_version: int = 1
    project_id: str
    snapshot_id: str
    started_at: datetime
    completed_at: datetime
    wall_clock_ms: int

    # Per-tier
    tier_s_calls: int
    tier_s_cost_usd: float
    tier_m_calls: int
    tier_m_cost_usd: float
    tier_l_calls: int
    tier_l_cost_usd: float
    embedding_calls: int
    embedding_cost_usd: float

    # Per-provider
    cost_by_provider: dict[str, float]    # {"anthropic": 7.20, "google": 1.50}

    # Per-operation
    cost_by_operation: dict[str, float]

    # Cache stats
    cache_hits: int
    cache_misses: int
    estimated_cost_saved_by_cache_usd: float

    # Render
    render_count: int
    render_total_ms: int
    render_failed: int

    # Job total
    total_cost_usd: float
```

`JobCostSummary` is the source-of-truth for the post-job cost breakdown UI and for the feedback-log derivation (per ADR-0014, the orchestrator's profile-prior re-derivation reads JobCostSummary as an input feature).

### Rate cards

Per-provider per-model rate cards as YAML files at `config/rate-cards/{provider}-{model}-{version}.yaml`. Example:

```yaml
# config/rate-cards/anthropic-claude-sonnet-4-7-v20260301.yaml
provider: anthropic
model: claude-sonnet-4-7
model_version: v20260301
effective_date: 2026-03-01
input_token_rate_usd_per_1k: 0.003
output_token_rate_usd_per_1k: 0.015
image_input_rate_usd_per_1k_tokens_equivalent: 0.003   # provider-specific normalization
```

Versioned per `model_version` from ADR-0007 (so cache key and rate card stay aligned). Shipped with the wheel; user manually updates on rate change. v1 may add a "fetch latest rates from a community-maintained rate-card repo" feature; out of scope for MVP.

### Dual-cap quota model (per Q6)

Two caps enforced together:

- **Total daily cap** — across all providers, all operations.
- **Per-provider daily caps** — separate cap per provider (e.g., Anthropic and Google each get their own).

A job is allowed to start only if **both** are satisfied for the estimated cost. Mid-job, if a cap is approached, the orchestrator pauses and surfaces the situation to the user (continue with reduced quality / cancel / raise the cap one-time-for-this-job).

#### SQLite quota state

Schema extension to ADR-0006:

```sql
CREATE TABLE quota_state (
    date           TEXT NOT NULL,            -- ISO date YYYY-MM-DD; partition key
    provider       TEXT NOT NULL,            -- "anthropic" / "google" / "local" / "_total_"
    spent_usd      REAL NOT NULL DEFAULT 0,
    last_updated   INTEGER NOT NULL,         -- UNIX timestamp
    PRIMARY KEY (date, provider)
);
```

Updated atomically on every `LLMCallEvent` write. The `_total_` row aggregates all providers for fast total-cap checks.

#### Quota enforcement

```python
async def check_quota(estimated_cost_per_provider: dict[str, float]) -> QuotaCheck:
    today_total = read_spent("_total_", today)
    total_cap = settings.spend_cap_total_usd
    per_provider_caps = settings.spend_cap_per_provider_usd  # dict
    estimated_total = sum(estimated_cost_per_provider.values())

    if today_total + estimated_total > total_cap:
        return QuotaCheck(allowed=False, reason="total_cap_would_be_exceeded")

    for provider, est in estimated_cost_per_provider.items():
        provider_today = read_spent(provider, today)
        provider_cap = per_provider_caps.get(provider)
        if provider_cap and (provider_today + est > provider_cap):
            return QuotaCheck(allowed=False, reason=f"{provider}_cap_would_be_exceeded")

    return QuotaCheck(allowed=True)
```

Called by the orchestrator before starting a job and before any heavy stage (5, 7) inside a job.

### First-time-setup configuration (per Q5)

The first-time-setup wizard (the user runs `impact-crater` for the first time) includes a **Spend cap** step:

```
Step 4 of 6 — Daily spend cap

Impact Crater can use third-party LLM APIs (Anthropic, Google) for
the heavy lifting. These have per-call costs. Set a daily spend cap
to protect against runaway jobs.

Total daily cap (across all providers): [ $___ ]   ← required
Per-provider caps (optional, finer-grained control):
  • Anthropic: [ $___ ]   (leave blank to use the total cap)
  • Google:    [ $___ ]   (leave blank to use the total cap)

You can change these later in Settings.
```

**No system default** for the total cap — the user **must** set it during setup. No silent zero-or-infinite default. Per-provider caps are optional; when blank, only the total cap applies.

The setup wizard refuses to proceed without a total-cap value entered. It validates: total ≥ $1, per-provider ≤ total.

Editable later via Settings.

### UI surfaces

Per A-015. Three surfaces:

1. **Pre-job cost preview.** When the user starts a new job:
   ```
   Estimated cost: $7.20 – $14.30 USD

   Breakdown by tier:
   • Embeddings (Google):           ~$0.40
   • Tier-S bulk (Google Flash):    ~$1.50 – $4.00
   • Tier-M structured (Sonnet):    ~$5.00 – $9.00
   • Tier-L narrative (Opus):       ~$0.30 – $1.30

   Today's remaining budget: $42.80 of $50.00 total
                              $30.20 of $35.00 Anthropic
                              $12.60 of $15.00 Google

   [ Start ]   [ Adjust effort level ↘ ]   [ Cancel ]
   ```

2. **In-job live spend.** During job processing, the in-progress UI shows running spend with the same breakdown, updating per `LLMCallEvent`.

3. **Post-job breakdown.** After Approve / Refine, the snapshot detail view shows the full `JobCostSummary` with cache-saved estimate and per-operation drill-down.

4. **Settings → Resource limits.** Editable spend caps; current month's daily history; rate-card versions in use.

### Telemetry retention + rotation

- **Telemetry events** in `telemetry.jsonl` are kept **forever by default** at MVP. Manual cleanup via Settings → Resource limits → "Archive telemetry older than [date]" button. v1 may add automatic rotation.
- **Feedback log** (per ADR-0014) follows the same policy.
- **JobCostSummary** persisted on snapshots; lives as long as the snapshot does (immutable per ADR-0006).
- **Quota state** rows can accumulate indefinitely (~1 row per provider per day, ~1KB/year). No rotation needed at MVP.
- **Rate-card files** are versioned; old versions kept indefinitely so old `LLMCallEvent` records can re-validate cost estimates.

### Effort levels (D-013 MVP)

L1, L2, L3 are pre-canned envelopes:

| Level | Photo cap | Video cap | Estimated cost (USD, single-provider routing) | Per-tier mix |
|---|---|---|---|---|
| L1 | ~10 | 1 (≤5 min) | $0.50 – $2 | mostly Tier-S; 1 Tier-L |
| L2 | ~100 | 10 (≤5 min each) | $2 – $7 | balanced |
| L3 | ~1000 | 50 (≤20 min each) | $7 – $22 (per ADR-0009) | full mix |

L4–L5 ship in v1.

The agentic max-permissible recommendation (per N-006) computes which levels fit the user's daily remaining budget (against both caps) and surfaces L_max with rationale: *"Based on your remaining daily budget of $42 and your typical L3 job costing ~$15, L3 is fine. L4 (~$50) would exceed your Anthropic per-provider cap."*

### Costs not covered

- **Local-LLM compute** (v1). When the local LLM lands per ADR-0008, "cost" becomes hardware utilization rather than dollars. ADR-0015's `LLMCallEvent.cost_estimate_usd` for `provider="local"` is always $0; a separate `local_compute_seconds` field gets added then.
- **Disk usage**. Tracked separately by the storage layer; ADR-0006 includes paths for project / cache / telemetry; cleanup is manual at MVP.
- **Network bandwidth**. Not tracked at MVP — the user pays their ISP either way.

## Alternatives considered

- **System default for the spend cap (e.g., $50/day).** Originally proposed. Rejected per Q5 — user-set during first-time setup is more honest about the user's responsibility for cost. No silent default that the user might forget about.
- **Single total-cap only.** Originally proposed. Rejected per Q6 — both total + per-provider gives finer control (e.g., user wants to limit Google spend specifically because of a tighter free-tier quota).
- **Per-provider-only caps (no total).** Considered. Rejected — the total cap is the simpler conceptual surface for "I don't want my daily AI spend to exceed $X"; per-provider is layered on top for users who care.
- **Telemetry to a remote service (anonymous usage analytics).** Rejected — self-hosted-first ethos. All telemetry stays local. v1 may add an opt-in "share aggregated usage stats with the maintainers" feature; not at MVP.
- **Auto-archive telemetry > 90 days.** Rejected at MVP — wait to see typical volumes; manual cleanup is fine for now.
- **Quota enforcement at the LLM client level (each call checks quota).** Considered but adds latency to every call. Pre-job + per-stage check is sufficient given the cost-estimate granularity.
- **Soft cap (warn but allow) vs hard cap (block).** ADR-0015 = hard cap with mid-job pause-and-prompt. The pause-and-prompt is the soft-cap-style escape hatch; the user can raise the cap one-time-for-this-job, otherwise the job pauses cleanly.
- **Effort levels as continuous slider (not L1/L2/L3 pre-canned).** Rejected per D-013 — pre-canned levels are easier to reason about; the agentic recommendation tells the user which level to pick.

## Consequences

- **The first-time-setup wizard becomes mandatory.** The user can't skip the spend-cap step. UI design needs to make this feel reasonable, not bureaucratic. Recommended copy emphasizes safety ("protects against runaway jobs") rather than friction.
- **Quota enforcement is pre-job + per-stage.** A job that fits in the budget at start can still pause mid-job if estimates were wrong (e.g., an unexpected Stage 9 refinement push). The pause-and-prompt is part of the failure-mode UX.
- **`JobCostSummary` is a load-bearing artifact for ADR-0014** — the orchestrator's profile-prior re-derivation reads it as a feature.
- **Cache hits show $0 cost in `LLMCallEvent`** but contribute to the `estimated_cost_saved_by_cache_usd` rollup, surfacing the cache value to the user.
- **Rate-card file shipping is one more thing to maintain.** When Anthropic or Google publishes a new rate, we ship a new rate-card YAML in the next release. Versioning by `model_version` keeps it correct.
- **Telemetry-rotation policy is deferred to v1**, but the schema is rotation-friendly (timestamps + correlation IDs make filtering/archiving straightforward).
- **Local-LLM cost model is a v1 ADR follow-on.** The `LLMCallEvent` schema has the hooks (`cost_estimate_usd`, `provider`); v1 adds the local-compute fields when the local-LLM runtime lands.
- **Feedback-log rotation** (also relevant to ADR-0014) follows the same MVP policy: keep forever; manual cleanup; v1 adds rotation.

## Linked items

- D-013 (effort levels — surfaced via the recommendation logic), A-004 (per-day spend cap — finalized here), A-015 (cost-transparency UI — schema for the events that feed it), N-006 (effort-level UX — agentic recommendation reads quota state).
- ADR-0005 (FastAPI process owns the telemetry-write path), ADR-0006 (telemetry path; SQLite `quota_state` table), ADR-0007 (`LLMCallEvent` shape), ADR-0009 (per-tier rate cards), ADR-0011 (per-stage cost), ADR-0013 (`ConnectorError` cost-transparency surface; YouTube quota status), ADR-0014 (`JobCostSummary` is a feature input for profile re-derivation; orchestrator-turn events tie cost to decisions).
- Cascades to: ADR-0016 (telemetry events for privacy-routing decisions surface via the same cost-transparency UI).
- Decision-log entry: D-034 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.3.3 in [`project/tasks/`](../../project/tasks/T-1.3.3.3-adr-0015-resource-accounting.md).
