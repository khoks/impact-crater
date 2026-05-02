# ADR-0008 — Local-LLM runtime slot (architecture-only at MVP)

**Status:** Accepted (deferred runtime selection — architecture only at this ADR)
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-28
**Phase:** scaffolding

## Context

D-016 commits to **remote-first MVP** with a v1 config flip to local-first routing. The v1 work is gated on the operation-aware router (N-002). ADR-0008's job at this phase is to lock the *interface* the v1 local runtime plugs into, so v1 work is "implement the slot," not "rewrite the abstraction."

The project mission (CLAUDE.md, RAW_VISION) caps local model size at **≤32B parameters**. Local-tier hardware ranges from "no GPU" to "RTX 4090 / 24 GB VRAM" with mid-range cards in between; the v1 runtime has to handle this range.

The local-LLM landscape is moving fast: Ollama, llama.cpp, vLLM, ExLlamaV2, MLX (Apple) are all candidates with different trade-offs. Locking the runtime at this ADR would commit us before we have the v1 N-002 findings to inform the choice.

## Decision

**A `LocalLLMClient` slot in the abstraction from ADR-0007. No implementation ships at MVP — the slot exists architecturally so v1 work is purely "implement the slot, ship the runtime, extend the routing config." The runtime selection is deferred to v1; Ollama is the recommended candidate, with llama.cpp and vLLM as alternatives kept open until v1 starts.**

Concretely:

### The slot

```python
class LocalLLMClient(LLMClient):
    """v1 implementation; MVP placeholder."""
    def __init__(self, runtime_config: LocalRuntimeConfig): ...
    # All LLMClient methods implemented against the runtime
```

The `LocalLLMClient` is registered in the same provider registry as `AnthropicLLMClient` and `GoogleLLMClient` (ADR-0007). At MVP, the registry contains only the two remote clients; at v1, the local client gets added with no protocol or call-site changes.

### MVP behavior

- Routing config (`config/llm-routing.yaml`) maps **no operations** to `provider: local`.
- The `LocalLLMClient` module exists as an empty stub (`backend/impact_crater/llm_clients/local.py`) with `NotImplementedError`-raising methods. This serves as the contract documentation: any v1 implementation must satisfy these signatures.
- Hardware detection (free VRAM, GPU class, CUDA / Metal / ROCm availability) is a v1 utility. MVP does not detect or report local-LLM capability.

### v1 candidate runtime — recommended: Ollama

Reasons:

- **Single-binary install** with cross-platform support (Windows / macOS / Linux).
- **OpenAI-compatible HTTP API** at `localhost:11434` — thin shim from the OpenAI client SDK; the `LocalLLMClient` becomes a small adapter.
- **Pull-by-name model management** (`ollama pull llava`); end-user UX matches the rest of the desktop-first ethos.
- **Active community** with vision-language model support (LLaVA, Qwen-VL, Llama-3.2-Vision, etc.) at the size classes we need (≤32B).

Alternatives kept open until v1:

- **llama.cpp Python bindings** — finer control, smaller dependency tree, but more glue code. Better fit if MVP-stress profiling shows we need batching control at the per-call level.
- **vLLM** — best throughput, but assumes server-class deployment patterns; overkill for desktop-first. Becomes interesting in the v3 hosted-service mode.
- **MLX** (Apple) — best fit on Apple Silicon. Optional path: ship MLX *and* Ollama, with the runtime chosen at startup based on platform.

The v1 selection criterion: pick the runtime that minimizes user friction for "install the app, get a local model running, run a curation job" against the ≤32B parameter cap. The N-002 work informs this with real per-operation hardware/quality data.

### v1 hardware-tier mapping (placeholder, locked at v1)

| VRAM tier | MVP behavior | v1 behavior |
|---|---|---|
| **No GPU** | Remote-only (default) | Remote-only (no change) |
| **8–12 GB** | Remote-only | Tier-S operations route to a ≤7B local vision-language model when remote quota is constrained; Tier-M / Tier-L stay remote |
| **16–24 GB** | Remote-only | Tier-S operations route to up to 13B local; Tier-M may route to local for batched workloads; Tier-L stays remote |
| **32+ GB** | Remote-only | Tier-S + Tier-M can route to up to 32B local; Tier-L stays remote (no local ≤32B model meets Opus-class quality reliably) |

Specific model lineup at each tier is locked at v1 alongside the N-002 router work. ADR-0009 already names the MVP remote models; the v1 ADR (placeholder ADR-NNNN, filed in v1) will name the local models.

### 32B parameter cap enforcement

The v1 `LocalLLMClient` reads model metadata at load time and refuses to load any model whose advertised parameter count exceeds 32B. This is a hard refusal with a clear error message — no override flag.

The cap is fixed by the project mission; revisiting it requires a vision-level discussion, not an architecture-level one.

### Failure model

The `LocalLLMClient` raises the same `LLMOperationFailed` exceptions as the remote clients (ADR-0007), with provider="local" and model = the loaded model name. Local failures are typically:

- Model not loaded / not pulled (pre-flight check at app start).
- Out-of-memory (the runtime should detect and surface; the v1 router can fall back to remote on OOM).
- Schema-validation failure on structured-output ops (smaller local models drift on schemas more than frontier remote models — the cache-key prompt_version absorbs the iteration).

## Alternatives considered

- **Lock the runtime now (Ollama at MVP).** Commits to a model lineup and runtime before we have the v1 N-002 router findings to inform the choice. The local-LLM landscape moves quickly enough that locking it now risks the runtime becoming a worse fit than alternatives by the time v1 work starts. Rejected — locking the *interface* now is sufficient.
- **No local-LLM slot in MVP at all.** Forces a refactor when v1 lands and breaks D-016's "abstraction in place from day one" commitment. Rejected.
- **Local-only as a deployment toggle without abstraction.** Would require parallel call sites for local vs. remote. Rejected — that's exactly the architectural rework D-016 forbids.
- **Multiple local clients (one per runtime).** Premature; the v1 work picks one, and adding a second is a registry-level addition once the protocol is locked. Deferred.
- **No 32B cap enforcement at the runtime layer.** Pushes the policy into config / docs / CI; weaker. The hard refusal at model-load time is the right place. Accepted.

## Consequences

- **v1 work to add local routing is "implement `LocalLLMClient` + ship the runtime + extend the routing config."** No protocol changes; no call-site changes.
- **The N-002 operation-aware router is the v1 unit of work** that turns the static routing dict into a smart resolver splitting ops between local and remote based on hardware/quota/cost.
- **Hardware detection is a v1 utility.** MVP does not need it.
- **The 32B cap is enforced at model-load time.** Refusal is hard; users with above-32B preferences can swap to a remote model via the routing config.
- **Adding multiple local runtimes (Ollama + llama.cpp + MLX) is supported by the registry** without protocol changes — implementations live side-by-side and the routing config picks one per op or globally.
- **MVP startup does not hit any local runtime.** No Ollama install required for MVP users; local routing is opt-in via v1 settings UX.

## Linked items

- D-016 (routing default — remote-first MVP, abstraction must exist), N-002 (operation-aware router — replaces the static dict in v1), CLAUDE.md mission (≤32B parameter cap), A-015 (cost-transparency UI — local routing changes the cost story), ADR-0007 (the `LLMClient` protocol the slot satisfies).
- ADR-0005 (Python process owns the slot), ADR-0006 (cache paths apply to local results too).
- Cascades to: ADR-0009 (v1 local-tier model lineup is a future ADR; MVP lineup names only remote models per this ADR's deferral).
- Decision-log entry: D-026 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.1.4 in [`project/tasks/`](../../project/tasks/T-1.3.1.4-adr-0008-local-llm-runtime-slot.md).
