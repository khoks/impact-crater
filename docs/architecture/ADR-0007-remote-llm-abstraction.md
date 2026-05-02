# ADR-0007 — Remote-LLM abstraction + MVP provider list

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-28
**Phase:** scaffolding

## Context

D-016 commits to **remote-first MVP** with the routing abstraction in place from day one, so v1's local-first config flip is not a rewrite. ADR-0007 fixes the abstraction shape and the MVP provider list.

The user's E-1.3 redirect (2026-04-28): **at least two providers at MVP** — the abstraction must be exercised under more than one shape from day one to validate it is genuinely pluggable. The user accepted Anthropic + Google as the MVP pair.

The abstraction has to support every operation the curation pipeline (D-009, N-001), agentic UX (D-013, A-015), and orchestrator (D-017) need. The N-002 operation-aware router (v1) plugs into this abstraction; the v1 work is implementing a smarter resolver, not changing the protocol.

## Decision

**A single `LLMClient` Python protocol with structured methods per operation type. Two implementations at MVP: `AnthropicLLMClient` and `GoogleLLMClient`. Routing dispatch is a static config dict `Operation -> (Provider, Model)` loaded from YAML; the v1 N-002 router replaces this dict with an agentic resolver against the same `Operation` taxonomy.**

### The `LLMClient` protocol

A Python `Protocol` (PEP 544 structural typing) defining every operation as a typed async method. Every call site uses the protocol; concrete provider implementations live behind it.

Methods (signature shapes; final type annotations locked at first feature work):

```python
class LLMClient(Protocol):
    # Embeddings
    async def embed_image(self, image_bytes: bytes, *, model_hint: str | None = None) -> Embedding: ...
    async def embed_text(self, text: str, *, model_hint: str | None = None) -> Embedding: ...

    # Vision-language captioning + scoring
    async def caption_image(self, image_bytes: bytes, *, prompt_template: str, params: dict) -> str: ...
    async def caption_video_scene(self, scene_frames: list[bytes], *, prompt_template: str, params: dict) -> str: ...
    async def score_image(self, image_bytes: bytes, *, dimension: str, params: dict) -> float: ...

    # Structured-output extraction (D-009 rich metadata)
    async def extract_metadata_image(self, image_bytes: bytes, *, schema: JSONSchema, params: dict) -> dict: ...
    async def extract_metadata_video_scene(self, scene_frames: list[bytes], *, schema: JSONSchema, params: dict) -> dict: ...

    # Narrative judgment (N-001)
    async def judge_narrative_arc(
        self, candidates: list[CandidateRef], *, brief: str, target_duration: int, params: dict
    ) -> ArcJudgment: ...

    # Brief parsing + agentic UX
    async def parse_user_brief(self, text: str, *, schema: JSONSchema, params: dict) -> dict: ...
    async def explain_cost(self, cost_breakdown: dict, *, params: dict) -> str: ...
    async def explain_upgrade_path(self, current_state: dict, target_level: int, *, params: dict) -> str: ...
    async def recommend_effort_level(self, project_state: dict, *, params: dict) -> EffortRecommendation: ...

    # Orchestrator (D-017) — tool-call-driven loop
    async def tool_call(self, tools: list[ToolSpec], messages: list[Message], *, params: dict) -> ToolCall: ...
    def stream_chat(
        self, messages: list[Message], *, tools: list[ToolSpec] | None = None, params: dict
    ) -> AsyncIterator[Token]: ...
```

Each method takes a `params` dict that the caller (orchestrator or pipeline stage) populates with the resolved provider/model from the routing dispatch — see below. Concrete provider implementations translate `params` + the typed args into provider-SDK-shaped calls (`anthropic.messages.create`, `google.generativeai.GenerativeModel.generate_content`, etc.).

### Routing dispatch

A central `LLMRouter` resolves an `Operation` to a `(Provider, Model)` pair via a static config:

```yaml
# config/llm-routing.yaml (default; overridable via settings table per ADR-0006)
embed_image:
  provider: google
  model: text-embedding-004      # or current Google embedding model at session time
caption_image:
  provider: google
  model: gemini-2.5-flash
extract_metadata_image:
  provider: anthropic
  model: claude-sonnet-4-7
score_image:
  provider: google
  model: gemini-2.5-flash
caption_video_scene:
  provider: google
  model: gemini-2.5-flash
extract_metadata_video_scene:
  provider: anthropic
  model: claude-sonnet-4-7
judge_narrative_arc:
  provider: anthropic
  model: claude-opus-4-7
parse_user_brief:
  provider: anthropic
  model: claude-sonnet-4-7
recommend_effort_level:
  provider: anthropic
  model: claude-sonnet-4-7
explain_cost:
  provider: anthropic
  model: claude-sonnet-4-7
explain_upgrade_path:
  provider: anthropic
  model: claude-sonnet-4-7
orchestrator_reasoning:
  provider: anthropic
  model: claude-sonnet-4-7
```

(The full per-operation rationale is in ADR-0009.)

Pseudocode for a call site:

```python
async def caption(media: MediaRef) -> str:
    op = "caption_image"
    provider_id, model = router.resolve(op)
    client = clients[provider_id]
    return await client.caption_image(
        await media.read_bytes(),
        prompt_template=prompts.get(op, provider_id, model),
        params={"model": model, "operation": op, "max_tokens": 200},
    )
```

The v1 N-002 router replaces `router.resolve(op)` with an agentic call that considers hardware availability, remote quota, and per-operation cost/quality trade-off. The protocol and call sites do not change.

### Provider list at MVP

- **Anthropic Claude** (`AnthropicLLMClient`)
  - Models in active use at MVP: `claude-sonnet-4-7`, `claude-opus-4-7`. Haiku is in the registry for future use; not used at MVP per ADR-0009's tier mapping.
  - Auth: `ANTHROPIC_API_KEY` env var (or `settings.anthropic_api_key` row in SQLite).
  - SDK: official `anthropic` Python SDK.
- **Google Gemini** (`GoogleLLMClient`)
  - Models in active use at MVP: `gemini-2.5-flash`, embedding model (current Google embedding model at session time). Gemini 2.5 Pro is in the registry for future use; not used at MVP per ADR-0009.
  - Auth: `GOOGLE_API_KEY` env var (or `settings.google_api_key`).
  - SDK: official `google-generativeai` Python SDK.

### Failure model

Each method has structured retry with exponential backoff and a hard ceiling. On hard failure, raise `LLMOperationFailed(operation, provider, model, attempts, last_error, cost_consumed_estimate)`. The orchestrator surfaces this through:

1. The cost-transparency UI (ADR-0015 / A-015) — partial work is recorded; the user sees what failed and what it cost.
2. The resume-after-failure path (A-005) — the persisted snapshot's `plan.json` records what's complete; the orchestrator restarts from there.
3. Provider-specific transient errors (HTTP 429, 5xx, network resets) trigger retry; permanent errors (HTTP 4xx other than 429, schema validation failures) raise immediately so they don't silently drain quota.

### Observability

Every call emits a structured event consumed by ADR-0015 (resource accounting):

```python
LLMCallEvent(
    timestamp, operation, provider, model, model_version,
    input_tokens, output_tokens, latency_ms,
    cost_estimate_usd, result_bytes_hash, project_id, snapshot_id,
)
```

Events are written to `~/.impact-crater/telemetry.jsonl` and aggregated for the cost-transparency UI.

### Caching

Read-through cache against the `cache_index` table per ADR-0006. Cache key:

```
sha256(content_hash + provider + model + model_version + operation + prompt_version + params_canonical)
```

Cache hits skip the provider call entirely. Cache misses populate the cache after a successful response. The `prompt_version` component means changing a prompt template invalidates only the entries that used the old template — A-011 / N-007 schema falls out cleanly.

## Alternatives considered

- **Single-provider MVP (Anthropic only).** Smaller surface area but doesn't validate the abstraction is genuinely pluggable. Rejected per user redirect.
- **Three-plus providers at MVP (e.g., add OpenAI).** Two providers is enough to validate; adding a third multiplies onboarding (auth, billing, eval prompts) for marginal value at MVP. Deferred to v1.
- **Single fat method `call_llm(operation: str, ...)` instead of typed methods.** Loses structured-output type safety and IDE support; turns mistakes into runtime errors. Rejected.
- **LangChain or similar abstraction wrapper.** Adds a layer and a dependency we don't need; our operations are specific and finite, and LangChain's flexibility costs control over prompt-versioning, caching, and observability shape. Rejected.
- **Per-call provider override via runtime arg `provider="anthropic"`.** Caller-side provider knowledge defeats the abstraction's purpose. The N-002 router is the documented way to influence routing. Rejected.
- **No protocol — concrete classes only with duck typing.** Loses static type checking; tools like `mypy` can't validate call sites. Rejected.
- **Embeddings via a separate `EmbeddingsClient` interface.** Splits the abstraction unnecessarily; embeddings are just another operation type. Rejected.

## Consequences

- **Adding a third provider in v1 is one new file** implementing `LLMClient` plus a registry entry. The N-002 work consumes the same protocol.
- **The static routing dict is the seed for the v1 agentic resolver.** No call-site changes when the router gets smarter.
- **All LLM calls are async-only.** Sync wrappers are explicit at boundaries (e.g., a CLI subcommand that doesn't run inside the FastAPI event loop).
- **Embeddings type is normalized** as `numpy.ndarray` with shape `(D,)` and `dtype=float32`. Cross-process pickle works without extra dependencies. Provider implementations convert from their native shape (Anthropic / Google return JSON arrays) into this format.
- **Each provider has its own auth.** Both keys are required at MVP for the app to operate at full capability. Single-provider mode is supported (gracefully degrade — route everything to the available provider, surface a UX warning when the missing provider would have been preferred).
- **Prompt templates per operation live in `prompts/{operation}/{provider}_{model}.jinja2`** referenced by the routing dispatch. `prompt_version` is a hash of the template content; changing a template invalidates only its cache entries.
- **Schema-validated structured-output operations** (`extract_metadata_*`, `parse_user_brief`, `recommend_effort_level`) reject responses that don't match the schema — surfaces provider drift early rather than corrupting downstream pipeline state.
- **Cost estimation is provider-specific.** Each `LLMClient` implementation maintains a per-model rate card and reports the estimated cost in each `LLMCallEvent`. The rate cards are versioned (provider rate changes get a new `model_version` to keep cache invalidation consistent).

## Linked items

- D-016 (routing default — remote-first MVP, abstraction must exist), D-017 (orchestrator harness — uses `tool_call` / `stream_chat`), D-009 (curation pipeline — operations enumerated here), D-013 + A-015 (cost-transparency UI — telemetry consumer), N-001 (narrative-arc judgment — `judge_narrative_arc`), N-002 (operation-aware router — replaces the static dict in v1), A-004 (per-day spend cap — telemetry consumer), A-007 (quality floor v1 — may add `score_*` operations).
- ADR-0005 (Python process owns the protocol), ADR-0006 (cache and telemetry paths).
- Cascades to: ADR-0008 (local-LLM slot uses the same protocol), ADR-0009 (per-operation model assignments), ADR-0011 (curation engine consumes the operations), ADR-0014 (orchestrator harness uses `tool_call` / `stream_chat`), ADR-0015 (resource accounting consumes `LLMCallEvent`).
- Decision-log entry: D-025 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.1.3 in [`project/tasks/`](../../project/tasks/T-1.3.1.3-adr-0007-remote-llm-abstraction.md).
