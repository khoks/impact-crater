# ADR-0009 — Cost-tiered per-operation model lineup at MVP

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-28
**Phase:** scaffolding

## Context

ADR-0007 fixed the LLM abstraction and named two MVP providers (Anthropic + Google). ADR-0009 names the **per-operation** model assignments — which provider+model handles which operation, at what tier, with what cost rationale.

The user's E-1.3 redirect (2026-04-28): **cost-tiering applies across every LLM operation, not only vision.** Apply the principle uniformly: pick the cheapest model that meets the quality bar for each operation; reserve the heavy-reasoning models for one-call-per-job heavy operations where prose / coherence quality matters most.

The MVP scale envelope is 1000 photos + 50 videos per job (D-012), 2–5 hour wall-clock ceiling (D-014). Per-op cost compounds at this scale: a Sonnet-class model on a 1000-photo bulk caption operation is roughly 30× more expensive than Flash for ~the same caption quality on a 1-line output. The savings on bulk operations fund a heavier model on the one operation where reasoning quality genuinely matters: narrative-arc judgment (N-001).

## Decision

**Three cost tiers, with a per-operation static routing table mapping every LLM operation to a tier (and thus a provider+model). Routing is loaded from `config/llm-routing.yaml` at startup; per-job overrides flow through the effort-level UX (D-013 / A-015).**

### The three tiers

| Tier | Model | Cost rationale | Use for |
|---|---|---|---|
| **Tier-S** (cheapest, bulk) | Gemini 2.5 Flash (Google) | Price-leader for vision-language at MVP-relevant quality; high throughput; generous rate limits | High-volume, low-stakes-per-call operations: caption, simple scoring, basic per-asset metadata |
| **Tier-M** (mid, structured) | Claude Sonnet 4.7 (Anthropic) | Best-in-class structured-output reliability; tool-use quality; mid cost-per-call | Structured-output operations where schema-match matters; agentic UX prose; the orchestrator's running tool-call loop |
| **Tier-L** (heavy reasoning) | Claude Opus 4.7 (Anthropic) | Top-tier reasoning + prose coherence; one-call-per-job is affordable | One-call-per-job heavy operations where prose quality + coherence matter most |

Embedding operations are not tiered along this S/M/L axis — they live under their own selection: **Google text-embedding-004** (or current Google embedding model at session time) for both image and text embeddings, picked for cost + quality at MVP scale.

### Per-operation MVP routing table

| Operation | Provider | Model | Tier | MVP volume per job | Rationale |
|---|---|---|---|---|---|
| `embed_image` | Google | `text-embedding-004` | (embedding) | per photo (1000) | Bulk; price-leader; quality sufficient for similarity / dedup |
| `embed_text` | Google | `text-embedding-004` | (embedding) | <10 per job | Same model handles text; small volume |
| `caption_image` | Google | `gemini-2.5-flash` | S | per photo (1000) | One-line caption; Flash is sufficient; Sonnet would be ~30× cost for marginal quality gain |
| `score_image` (quality, narrative-value) | Google | `gemini-2.5-flash` | S | per photo (1000), per dimension | Float-out scoring; cheap rubric prompt; bulk-friendly |
| `extract_metadata_image` | Anthropic | `claude-sonnet-4-7` | M | per photo (1000) | D-009 rich schema (people, location, mood, lighting, quality, activity, objects, clothing, pose, tags) — schema-match reliability matters |
| `caption_video_scene` | Google | `gemini-2.5-flash` | S | per scene (~500) | Same reasoning as image caption |
| `extract_metadata_video_scene` | Anthropic | `claude-sonnet-4-7` | M | per scene (~500) | Same reasoning as image metadata |
| `parse_user_brief` | Anthropic | `claude-sonnet-4-7` | M | 1 per job | Structured output drives the whole downstream pipeline; reliability matters more than cost on a one-call op |
| `recommend_effort_level` | Anthropic | `claude-sonnet-4-7` | M | 1 per job | Agentic UX call; prose + structured recommendation |
| `explain_cost` | Anthropic | `claude-sonnet-4-7` | M | <5 per job | Agentic prose UX (A-015 cost-transparency surface) |
| `explain_upgrade_path` | Anthropic | `claude-sonnet-4-7` | M | <2 per job | Agentic prose UX (A-015) |
| `judge_narrative_arc` | Anthropic | `claude-opus-4-7` | L | 1 per job | The N-001 novel mechanism; reasoning + coherence quality matters most; one heavy call is affordable |
| `orchestrator_reasoning` (D-017 tool-call loop) | Anthropic | `claude-sonnet-4-7` | M | running per job (~20–80 turns) | Structured tool calls; Sonnet quality is sufficient; reserve Opus for `judge_narrative_arc` where it matters |

Note that `segment_video_scenes` is **not** an LLM operation — it runs deterministically (PySceneDetect) per ADR-0010 (round 2). The per-scene metadata + caption operations apply *after* deterministic segmentation produces the scene list.

### Per-job MVP cost envelope (rough estimates)

These are first-pass estimates for engineering planning, not user-facing commitments. The cost-transparency UI (ADR-0015 / A-015) reports actual cost from telemetry events; the values below feed the effort-level recommendation logic (D-013, N-006).

Assuming MVP scale = 1000 photos + 50 videos with avg 10 scenes/video:

| Tier | Op count per job | Per-op cost (USD, order of magnitude) | Tier total per job |
|---|---|---|---|
| Embedding | ~1010 calls | ~$0.0001 / 1k tokens of input | < $0.50 |
| Tier-S (Flash) | ~3500 calls | ~$0.001 / call (image input dominates) | $1–5 |
| Tier-M (Sonnet) | ~1500 calls + ~80 orchestrator turns | ~$0.005 / call | $5–15 |
| Tier-L (Opus) | 1 call | ~$0.50 / call (large input, structured output) | < $1 |
| **Total per-job estimate** | | | **$7–22 USD per job** |

Numbers are pre-prompt-engineering and pre-cache-hit; A-011 cross-job cache reuse will reduce repeat-job cost substantially (re-running a curation against the same media re-uses Tier-S + embedding cache entries entirely; Tier-M re-uses for unchanged metadata extractions; Tier-L always re-runs because the brief / target duration may differ).

### Routing config shape

`config/llm-routing.yaml` ships with the table above. Loaded by the `LLMRouter` (ADR-0007) at startup. Per-user overrides via `settings.routing_overrides` (SQLite per ADR-0006). Per-job overrides via the effort-level UX (D-013): "always-Opus" / "always-Flash" / per-op-select buttons inside the user's hardware/quota envelope.

The v1 N-002 operation-aware router replaces the static lookup with an agentic resolver that considers hardware availability, remote quota, and per-operation cost/quality trade-off — the same `Operation` taxonomy and routing-config schema.

### Local-tier (v1)

When ADR-0008's `LocalLLMClient` is implemented in v1, Tier-S operations route to a local model when hardware permits. Tier-M may route to local for batched workloads if a ≤32B local model meets the quality bar (tested per-op in v1). Tier-L stays remote — no ≤32B model meets Opus-class reasoning reliably as of session time.

The v1 routing config gets a `local_eligible: true|false` flag per operation; the N-002 router consults this flag plus hardware availability plus current quota state to decide per-call. The MVP routing config sets `local_eligible: false` everywhere; v1 flips relevant flags.

## Alternatives considered

- **One model for everything (e.g., Sonnet across the board).** Wastes the bulk cheap operations on a mid-tier model — ~30× cost overhead on the 3500 Tier-S calls per job. Rejected per user redirect.
- **Anthropic-only with Haiku for bulk.** Defensible (Haiku is cheap), but loses the multi-provider abstraction validation that ADR-0007 mandates. Gemini Flash at S-tier is at-or-below Haiku cost at MVP-relevant quality and exercises the provider boundary. Rejected.
- **Always-Opus for the orchestrator.** Orchestrator is the running session per job (~20–80 turns); per-call cost compounds. Sonnet quality is sufficient for tool dispatch and structured output. Reserve Opus for the one heavy-judgment call where it matters. Rejected as default.
- **Per-operation model picks made by the user upfront.** Too much UX complexity for MVP; the static config is fine. Per-job effort-level overrides (always-Opus / always-Flash) cover the cases that matter. Rejected for MVP; full per-op user customization is a v1 settings UI.
- **Cost-tier as a runtime parameter ("cheap mode" / "quality mode") rather than per-op static.** Loses the explicit per-op rationale; users get a black-box quality slider. The static per-op assignment is more honest about what's happening. Rejected.
- **Use Gemini for the mid-tier as well (Gemini 2.5 Pro) instead of Sonnet.** Pro is competitive for some operations; rejected because Sonnet's structured-output reliability and tool-use quality are more proven at session time, and the MVP's two-provider mandate is satisfied with Anthropic-mid + Google-bulk + Anthropic-heavy. Revisit at v1 with measured eval data.
- **Skip the cost-transparency UI at MVP.** A-015 has cost-transparency UI as MVP scope (the agentic explanation, the running spend); skipping would require a D-NNN reversal. Out of scope here.

## Consequences

- **Cost story per job is bounded** by the table above. The A-004 per-day spend cap consumes the cost-estimation events from the routing dispatch.
- **v1 N-002 router** replaces the static table with a runtime resolver against the same `Operation` taxonomy and YAML schema.
- **Adding a new operation** requires updating ADR-0009, the routing config, and (often) a new prompt template. Small ceremony but explicit; prevents operations from sneaking in without a tier assignment.
- **Prompt-engineering work happens per operation** in `prompts/{operation}/{provider}_{model}.jinja2` (ADR-0007). Different providers may need different prompt phrasings to reach the schema-match target.
- **The 32B local-tier (v1)** replaces only Tier-S calls with local when hardware permits. Tier-M and Tier-L stay remote at v1 because no ≤32B local model meets Sonnet/Opus quality reliably; this assumption is re-evaluated as the local-LLM landscape evolves.
- **Cache hit rate is highest on Tier-S + embedding ops** (deterministic content-keyed reuse across jobs). Tier-M cache hits when a user re-curates the same media without changing the metadata schema. Tier-L always re-runs because the brief and target duration are per-job inputs.
- **Provider rate-card drift** (Google or Anthropic changing prices) is absorbed by `model_version` in the cache key and the per-provider rate-card files (ADR-0007); changing a rate is a versioned config update, not a code change.
- **Single-provider degraded mode** (one of the two API keys missing) routes everything to the available provider with a UX warning; the cost estimates above shift accordingly.

## Linked items

- D-009 (curation pipeline — operation taxonomy lives here), D-013 (effort-level UX — per-job overrides), D-016 (routing default), D-017 (orchestrator — uses Tier-M), N-001 (narrative-arc judgment — Tier-L), N-002 (operation-aware router future — replaces static dict), N-006 (effort-level UX), A-004 (per-day spend cap — telemetry consumer), A-007 (quality floor v1 — may rebalance Tier-S for floor adherence), A-011 (cross-job cache — reduces repeat cost), A-015 (cost-transparency UI — telemetry consumer).
- ADR-0005 (Python process), ADR-0006 (cache + telemetry paths), ADR-0007 (`LLMClient` protocol + routing dispatch shape), ADR-0008 (local-tier slot — v1 local mappings extend this table).
- Cascades to: ADR-0011 (curation engine — references the routing table), ADR-0014 (orchestrator — uses Tier-M), ADR-0015 (resource accounting — telemetry schema feeds A-015).
- Decision-log entry: D-027 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.1.5 in [`project/tasks/`](../../project/tasks/T-1.3.1.5-adr-0009-cost-tiered-model-lineup.md).

## Amendments

### 2026-10-25 — current pins; `config/llm-routing.yaml` is the source of truth (S-2.13.5)

The table in the Decision names Sonnet 4.7 / Opus 4.7 / `text-embedding-004`; none of those is routed. **`config/llm-routing.yaml` is the single source of truth for which model serves which operation.** The table below is a dated snapshot of it (S-2.10.9, 2026-10-25 — the D-061 lineup): pinned `model_version` tokens (release dates) instead of `latest` / `v1`, a rate card for every routed model (`tests/test_routing_config_integrity.py` enforces both), and a pre-spend availability ping (`LLMRouter.verify_routes`, run by `build_router_from_settings` before every job and by the wizard's key test). After S-2.13.7 the yaml routes nine operations. The previous snapshot (PR #72, 2026-07-01, S-2.10.7) was `gemini-embedding-001` / `gemini-2.5-flash` / `claude-sonnet-4-6` / `gemini-2.5-flash-image` / `claude-opus-4-8`, all at `latest` / `v1`.

| Operation(s) | Tier | Provider | Model | `model_version` | Notes |
|---|---|---|---|---|---|
| `embed_image`, `embed_text` | embedding | google | `gemini-embedding-2` | `2026-04-22` | the image bytes are embedded directly (768-d MRL output, one space shared with text); replaces caption-then-embed (ADR-0018 amendment). Vectors are incompatible with `gemini-embedding-001`, so the Stage 4 cosine threshold is re-tuned on the Zion fixture (S-3.10.1) |
| `caption_image`, `score_image`, `generate_title_text` | S | anthropic | `claude-haiku-5-5` | `2026-10-07` | `effort: low`; `score_image` calls the strict `submit_score` tool, the title text calls `submit_metadata` (not strict — see the shipped note). Configured fallback: `gemini-3.5-flash-lite` (`thinking_level: minimal`) — its prompts and rate card are shipped |
| `extract_metadata_image`, `parse_user_brief` | M | anthropic | `claude-haiku-5-5` | `2026-10-07` | `effort: low`, `max_tokens` 4096 (thinking counts toward it); A/B-gated against the cached Sonnet 4.6 metadata with `claude-sonnet-5-5` as the hedge (D-061). `extract_metadata_image` also serves video-scene frames (video-scene schema); `parse_user_brief` also carries Stage 0.5 brief intent, the Stage 6.5 second-guess and the Stage 9 refinement planner |
| `generate_title_background` | M | google | `gemini-3.1-flash-lite-image` | `2026-06-30` | opt-in title-card image, 16:9 at 1K via `image_config`, $0.0336 per image (`per_call_rate_usd` on the card) |
| `judge_narrative_arc` | L | anthropic | `claude-opus-5-5` | `2026-09-21` | `effort: high` (thinking cannot be disabled; the default would be `medium`), `max_tokens` 20000 — thinking counts toward it, and the value stays under the SDK's non-streaming ceiling. `temperature` is never sent to Anthropic any more |

Removed by S-2.13.7 (routed, never dispatched, no router method): `recommend_effort_level`, `explain_cost`, `explain_upgrade_path`, `orchestrator_reasoning` (ADR-0021), `caption_video_scene`, `extract_metadata_video_scene`. Never routed, never built: `analyze_music_duration_mismatch` (ADR-0012 amendment).

Also true today: `model_version: latest` on the Anthropic operations means a provider-side model roll does **not** invalidate cached results — the reason S-2.10.9 pins a real token; `pipeline/runner.py::_TIER_BY_OPERATION` mirrors this yaml for `JobCostSummary`; telemetry puts roughly 99 % of spend on Anthropic (S-2.13.8). Everything else in this ADR stands — three tiers, cheapest model that meets the bar, Tier-L reserved for the single judge call, a static table until the N-002 router. The cost envelope loses its "~80 orchestrator turns" line (ADR-0021).

### 2026-10-25 — Phase 1 targets (D-061)

The pins above are what runs today. D-061 decides what S-2.10.9 bumps them to, after running both providers' list-models endpoints with the owner's keys and reading the official pricing and deprecation pages on 2026-10-25:

| Tier / role | Today | Target | `model_version` | Fallback |
|---|---|---|---|---|
| S — captions, scores | `gemini-2.5-flash` | `claude-haiku-5-5`, `effort: low` | `2026-10-07` | `gemini-3.5-flash-lite`, `thinking_level: minimal` |
| M — metadata, brief, second-guess, refinement planner, title text | `claude-sonnet-4-6` | `claude-haiku-5-5`, `effort: low` (A/B-gated) | `2026-10-07` | `claude-sonnet-5-5`, `effort: low` |
| L — judge | `claude-opus-4-8` | `claude-opus-5-5`, `effort: high` | `2026-09-21` | `claude-fable-5-1` only on eval evidence |
| embedding | `gemini-embedding-001` (caption text) | `gemini-embedding-2` (image bytes) | `2026-04-22` | — |
| image generation | `gemini-2.5-flash-image` (shutdown 2027-03-15) | `gemini-3.1-flash-lite-image` | `2026-06-30` | `gemini-nano-banana-2.1` (2K) |

**Shipped 2026-10-25 (S-2.10.9).** The yaml, the prompts (`prompts/<op>/anthropic_claude-haiku-5-5.jinja2`, `anthropic_claude-opus-5-5.jinja2`, `google_gemini-3.1-flash-lite-image.jinja2`; the Google Tier-S templates renamed to `google_gemini-3.5-flash-lite.jinja2` as the configured fallback) and six rate cards landed with the client constraints: `temperature` is never sent to Anthropic; `effort` flows from the yaml to `output_config.effort` (Anthropic) / `thinking_config.thinking_level` (Google); `submit_score` is a strict tool, `submit_metadata` is not — the D-009 metadata schema exceeds Anthropic's strict limits (map-typed `pose_quality_scores`, more than 24 optional parameters, tuple fields), so the prompt asks for the call, a text-only reply is retried once and the pydantic parse validates the result; `refusal` / `model_context_window_exceeded` / `max_tokens` stop reasons raise readable failures that `jobs/runner_glue._classify_failure` maps, as does a retired model ID; Gemini image and thinking tokens are metered from `usage_metadata`; the two Opus rate cards were corrected to $5 / $25; `_ballpark_cost` prices per-image ops from the card's `per_call_rate_usd`. Tier-M stays A/B-gated (D-061).

Two corrections to this ADR's cost assumptions: the Opus rate cards in `config/rate-cards/` carry $15 / $75 per 1M, three times the official Opus 4.5 / 4.8 price of $5 / $25, so every Tier-L figure derived from them (including the "per-job MVP cost envelope" above and the SW-US run's $2.67 judge cost) is overstated; and Gemini image input tokens are not captured by the telemetry, so the Tier-S share of past bills is unknown. Both are fixed in S-2.10.9. With the target lineup a 1,663-asset job is expected to cost ≈ $2–3 in AI calls instead of ≈ $17–20.
