# ARCHITECTURE.md — Impact Crater system architecture

> **Status: round 1 of E-1.3 complete (2026-04-28).** Foundation + LLM stack locked (ADR-0005..0009 / D-023..D-027). Round 2 (media + curation) and round 3 (connectors + harness + cross-cutting) still pending; their sections below retain "to decide" placeholders.

The accepted decisions live in this folder as `ADR-NNNN-*.md` files. As of 2026-04-28: nine ADRs accepted (license, work-tracking, skills, auto-merge policy, process topology + language stack, storage layout, remote-LLM abstraction, local-LLM runtime slot, cost-tiered per-operation lineup); seven still open and to be filed in rounds 2 + 3 of E-1.3.

---

## Component map

The eventual diagram covers, at minimum, these layers:

1. **Client / UI** — where the user uploads media, types the brief, reviews previews, and approves publishes. **TypeScript + React** served from the FastAPI process per [ADR-0005](./ADR-0005-process-topology-language-stack.md).
2. **Project & media library** — the persistent store of the user's source media, organized by project. **Per-project tree under `~/.impact-crater/projects/{project_id}/` with SQLite metadata, content-hash-referenced source media, snapshot directories per N-003** per [ADR-0006](./ADR-0006-storage-layout.md).
3. **Analysis pipeline** — the path from raw media to per-asset metadata: scene detection, perceptual hashing, face/people detection, location clustering, quality scoring, vision-LLM captions and tags. *(Round 2 — to be filed as ADR-0010.)*
4. **Curation engine** — the path from per-asset metadata to a sequenced set of artifact-specific selections, including the N-001 narrative-arc judgment stage. *(Round 2 — to be filed as ADR-0011.)*
5. **Render pipeline** — the path from selections to rendered artifacts: video clipping, transitions, aspect-ratio handling, music alignment, photo cropping. *(Round 2 — music alignment as ADR-0012; render pipeline details land alongside ADR-0010 / ADR-0011.)*
6. **Agent harness** — the orchestrator-driven natural-language interface (single orchestrator per D-017; tool-call shape filed in round 3 as ADR-0014).
7. **LLM client + router** — every LLM call goes through the **`LLMClient` Python protocol** with provider implementations behind it (Anthropic + Google at MVP) and a static **routing dispatch** mapping operations to providers/models per [ADR-0007](./ADR-0007-remote-llm-abstraction.md), [ADR-0008](./ADR-0008-local-llm-runtime-slot.md) (local slot, architecture-only at MVP), [ADR-0009](./ADR-0009-cost-tiered-model-lineup.md) (per-op cost-tiered lineup).
8. **Connector layer** — the adapters with the explicit-consent publish gate. *(Round 3 — to be filed as ADR-0013.)*
9. **Profile / theme store** — the gradually-learned record of the user's style, themes, and inspiration sources. *(v1 work, not MVP — A-014.)*

**Process topology** (locked in [ADR-0005](./ADR-0005-process-topology-language-stack.md)): single primary FastAPI process running on `localhost`, hosting the orchestrator, the LLM client abstraction, project state management, and serving the built React frontend as static assets. Heavy lifting via Python subprocess workers spawned by the orchestrator with an in-process queue at MVP. Packaging: `pip install impact-crater` + `impact-crater` CLI.

---

## LLM strategy

The user's hard constraint: local model size capped at ≤32B parameters per CLAUDE.md mission. The router must work on machines ranging from "no GPU, cloud-only" to "RTX 4090 / 24 GB VRAM, can host a 32B model locally" with intermediate states (smaller GPUs) handled gracefully. MVP routes remote-only (D-016); v1 adds local-first routing via the operation-aware router (N-002).

**Abstraction** — every LLM call goes through a single `LLMClient` Python `Protocol` with typed async methods per operation (embed, caption, score, extract_metadata, judge_narrative_arc, parse_user_brief, recommend_effort_level, explain_cost, explain_upgrade_path, tool_call, stream_chat). See [ADR-0007](./ADR-0007-remote-llm-abstraction.md). Local runtime plugs into the same protocol via a `LocalLLMClient` slot; see [ADR-0008](./ADR-0008-local-llm-runtime-slot.md).

**MVP provider list:**
- **Anthropic Claude** — `claude-sonnet-4-7` (Tier-M structured output + agentic UX + orchestrator), `claude-opus-4-7` (Tier-L narrative-arc judgment).
- **Google Gemini** — `gemini-2.5-flash` (Tier-S bulk caption + scoring), `text-embedding-004` for embeddings.

**Routing dispatch** — a static YAML config at `config/llm-routing.yaml` mapping each `Operation` to `(provider, model)`. Loaded at startup. Per-user overrides in SQLite settings. Per-job overrides via the effort-level UX (D-013). The v1 N-002 router replaces this static lookup with an agentic resolver against the same `Operation` taxonomy and YAML schema. See [ADR-0009](./ADR-0009-cost-tiered-model-lineup.md) for the per-operation routing table and the Tier-S / Tier-M / Tier-L cost rationale.

**Failure model** — structured retry + hard ceiling per call site; on permanent failure the orchestrator surfaces the partial work via the cost-transparency UI (A-015) and the resume-after-failure path (A-005) reads the persisted snapshot's `plan.json` to know what's done. See ADR-0007 for `LLMOperationFailed` shape.

**32B local-tier (v1)** — replaces Tier-S calls with a local model when hardware permits; selectively replaces Tier-M when a ≤32B local model meets the schema-match quality bar. Tier-L stays remote — no ≤32B model meets Opus-class reasoning reliably as of session time. See [ADR-0008](./ADR-0008-local-llm-runtime-slot.md) for the v1 hardware-tier mapping placeholder; specific local model names are locked at v1 alongside the N-002 router work.

---

## Media pipeline (placeholder)

The lower-level path that runs before any LLM sees media. Quick, deterministic, and cheap.

**To decide:**
- Photo decoding and format coverage (JPEG, HEIC, RAW formats, AVIF, etc.).
- Video decoding (containers and codecs to support; what we transcode on ingest).
- Perceptual hashing approach for dedup.
- Face / people detection model choice (and whether it runs by default or behind a privacy toggle).
- Scene detection for video (cut detection + per-shot quality score).
- Aspect-ratio normalization and smart-crop strategy.
- Where rendering work happens (in-process, sidecar process, container).

---

## Curation engine (placeholder)

The per-artifact selection logic — what photos go in the album, what clips form the reel, the narrative arc of a journey video.

**To decide:**
- Selection algorithm shape: deterministic pipeline (embed → cluster → score → arc planner) vs. LLM-as-curator (single multimodal pass) vs. hybrid.
- Feature representation: dense embeddings (which model), discrete attributes (faces / locations / tags), or both.
- Narrative-arc model: rule-based templates per artifact type, learned from inspiration links, or LLM-generated.
- Music alignment: licensed-library API, generated, or user-supplied — and the energy / beat-matching rules.

---

## Storage

Locked in [ADR-0006](./ADR-0006-storage-layout.md). Summary:

- **Application root:** `~/.impact-crater/` (overridable via `IMPACT_CRATER_HOME`).
- **Per-project tree** at `~/.impact-crater/projects/{project_id}/` with `manifest.json`, `sources/` (JSON sidecars per source media), `snapshots/{snapshot_id}/` (immutable per-render directories — `plan.json`, `metadata/`, `candidates/`, `render.mp4`, `parent.txt`), `renders/`, `cache/`. Snapshot directories are the **N-003 substrate**: each preview/refine writes a new snapshot whose `parent.txt` points at its predecessor; refine chains are the natural data model A-006 (multi-version comparison) consumes when it lands in v1.
- **Metadata: SQLite** at `~/.impact-crater/db/impact-crater.sqlite`. Tables: `projects`, `media`, `project_media`, `snapshots`, `audit`, `settings`, `cache_index`. Async access via `aiosqlite`; migrations via Alembic when code lands.
- **Source media: referenced, not copied.** `media.source_path` + `media.content_hash` (SHA-256). Path-moved fallback = content-hash search across known media roots, with a re-link prompt.
- **Cross-project cache** at `~/.impact-crater/cache/{content_hash}/{provider}_{model}_{version}/...` driving A-011 / N-007 reuse. Cache key = sha256(content_hash + provider + model + model_version + operation + prompt_version + params_canonical).
- **Append-only JSONL audit log** at `~/.impact-crater/audit.jsonl` for A-003 publishing audit; mirrored in the SQLite `audit` table for query convenience. JSONL is the authoritative record (append-only file > database row for crash safety).
- **v3 hosted-service mode** swaps disk → object storage and SQLite → Postgres without schema changes.

---

## Connectors (placeholder)

The publish-side adapters. Default policy: official APIs only, behind an explicit per-publish consent gate.

**To decide:**
- Initial connector set for the MVP.
- OAuth vs. user-token credential model.
- Audit-log shape (what gets logged, where, with what retention).
- Behavior when an API rejects an artifact (size, format, content policy).

---

## Agent harness (placeholder)

The user-facing natural-language dialogue that drives the system end-to-end.

**To decide:**
- Single agent vs. multi-agent (e.g. planner + media-analyst + editor).
- Tool surface: what tools the agent calls into.
- Memory model: how state from one turn carries to the next within a project.
- Failure mode: what the user sees when the agent gets stuck.

---

## Cross-cutting concerns

- **Resource accounting.** GPU minutes, remote-LLM tokens, disk usage — surfaced to the user with hard ceilings. (ADR pending.)
- **Privacy posture.** Default boundaries on what leaves the device. (ADR pending.)
- **Reproducibility.** Re-running curation on the same project should give a stable result.
- **Cancellation.** Long jobs (5000-photo curation) must be cancellable and resumable.
- **Telemetry.** Local-only by default; opt-in if anything ever leaves the device.

---

## Accepted ADRs (as of E-1.3 round 1, 2026-04-28)

- [ADR-0001-license.md](./ADR-0001-license.md) — Business Source License 1.1 with Change Date 2030-04-25.
- [ADR-0002-work-tracking-hierarchy.md](./ADR-0002-work-tracking-hierarchy.md) — Four-level Initiative → Epic → Story → Task with hierarchical IDs and file-per-item layout.
- [ADR-0003-session-housekeeping-skills.md](./ADR-0003-session-housekeeping-skills.md) — Two project-local Claude Code skills auto-invoked on `Stop`, with a branch+PR-to-master flow. ("Never auto-merge" clause superseded by ADR-0004.)
- [ADR-0004-skill-pr-auto-merge.md](./ADR-0004-skill-pr-auto-merge.md) — All Claude-generated PRs auto-merge with `gh pr merge --squash --delete-branch --admin`.
- [ADR-0005-process-topology-language-stack.md](./ADR-0005-process-topology-language-stack.md) — Backend = Python 3.11+ / FastAPI; frontend = TypeScript + React; subprocess workers for heavy lifting; `pip install impact-crater` packaging.
- [ADR-0006-storage-layout.md](./ADR-0006-storage-layout.md) — Per-project tree under `~/.impact-crater/projects/`; SQLite for metadata; source media referenced (path + SHA-256); snapshot directories per N-003; cross-project content-hash cache; append-only JSONL audit log.
- [ADR-0007-remote-llm-abstraction.md](./ADR-0007-remote-llm-abstraction.md) — `LLMClient` Python protocol with typed async methods per operation; MVP provider list = Anthropic + Google; static YAML routing dispatch (the v1 N-002 router replaces this with an agentic resolver).
- [ADR-0008-local-llm-runtime-slot.md](./ADR-0008-local-llm-runtime-slot.md) — `LocalLLMClient` slot in the same registry; MVP ships an empty stub; v1 candidate runtime = Ollama; ≤32B parameter cap enforced at model-load time.
- [ADR-0009-cost-tiered-model-lineup.md](./ADR-0009-cost-tiered-model-lineup.md) — Three cost tiers (S = Gemini 2.5 Flash, M = Claude Sonnet 4.7, L = Claude Opus 4.7); per-operation static routing table assigning every operation to a tier; Tier-L reserved for the one-call-per-job N-001 narrative-arc judgment.

## Pending ADRs (rounds 2 + 3 of E-1.3)

- ADR-0010 — Media pipeline framework (decoders, perceptual hash, scene detection, smart-crop). *Round 2.*
- ADR-0011 — Curation engine algorithm shape (formalize D-009 hybrid pipeline + N-001 narrative-arc into stages with input/output schemas). *Round 2.*
- ADR-0012 — Music alignment strategy (formalize D-010 + D-018 + A-013). *Round 2.*
- ADR-0013 — Connector layer credential model + audit-log shape (YouTube only at MVP per D-007). *Round 3.*
- ADR-0014 — Agent harness topology (formalize D-017 single orchestrator with concrete tool surface). *Round 3.*
- ADR-0015 — Resource accounting + quota model (formalize D-013 + A-004 + A-015 telemetry schema). *Round 3.*
- ADR-0016 — Privacy posture defaults (formalize A-002 + D-016 user-facing flow). *Round 3.*
