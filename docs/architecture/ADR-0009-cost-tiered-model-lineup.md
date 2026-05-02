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
