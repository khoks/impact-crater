# ARCHITECTURE.md — Impact Crater system architecture

> **Status: stub.** This file gets filled in during the architecture-grooming session (Epic `E-1.3`). Until then, it is a *map of the rooms we will furnish*, not the architecture itself. Each section below ends with a "to decide" list; those decisions become ADRs.

The accepted decisions live in this folder as `ADR-NNNN-*.md` files. Three are already accepted at scaffolding time (license, work-tracking shape, session-housekeeping skills); the rest are open.

---

## Component map (placeholder)

The eventual diagram will cover, at minimum, these layers:

1. **Client / UI** — where the user uploads media, types the brief, reviews previews, and approves publishes.
2. **Project & media library** — the persistent store of the user's source media, organized by project (= a trip / event / shoot).
3. **Analysis pipeline** — the path from raw media to per-asset metadata: scene detection, perceptual hashing, face/people detection, location clustering, quality scoring, vision-LLM captions and tags.
4. **Curation engine** — the path from per-asset metadata to a sequenced set of artifact-specific selections (which photos for the album, which clips for the reel, the narrative arc of the journey video).
5. **Render pipeline** — the path from selections to rendered artifacts: video clipping, transitions, aspect-ratio handling, music alignment, photo cropping.
6. **Agent harness** — the LLM-orchestrated dialogue that takes the user's natural-language brief, drives the curation engine, and accepts user feedback to re-curate or re-render.
7. **LLM router** — the runtime decision between local-hosted and remote API LLMs based on hardware capability and quota.
8. **Connector layer** — the adapters to Instagram, Facebook, X, YouTube, etc. with the explicit-consent publish gate.
9. **Profile / theme store** — the gradually-learned record of the user's style, themes, and inspiration sources.

**To decide (each becomes an ADR):**
- Process topology: monolith vs. service split. Which boundaries justify a service?
- Storage layout: how source media is referenced (path + content-hash), where derived artifacts live, what the project unit looks like on disk.
- Async pipeline framework: what queues / workers run the long-tail analysis jobs.

---

## LLM strategy (placeholder)

The user's hard constraint: local model size capped at ≤ 32B parameters. The router must work on machines ranging from "no GPU, cloud-only" to "RTX 4090 / 24 GB VRAM, can host a 32B model locally" with intermediate states (smaller GPUs) handled gracefully.

**To decide (each becomes an ADR):**
- The local-model runtime (e.g. llama.cpp, vLLM, Ollama) and the criteria for choosing.
- The vision-model lineup at each capability tier.
- The remote-LLM provider list (default: Anthropic Claude) and the abstraction boundary.
- The router decision rule: per-task, per-job, per-step? Cost-floor and latency-ceiling parameters.
- Fallback behavior on remote-quota exhaustion.

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

## Storage (placeholder)

**To decide:**
- Project filesystem layout on disk.
- Database (or none) for metadata, embeddings, and curation results.
- Whether source media is copied into the project or referenced in place.
- Cache / temp policy for derived assets (thumbnails, embeddings, intermediate renders).

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

## Accepted ADRs (as of scaffolding)

- [ADR-0001-license.md](./ADR-0001-license.md) — Business Source License 1.1 with Change Date 2030-04-25.
- [ADR-0002-work-tracking-hierarchy.md](./ADR-0002-work-tracking-hierarchy.md) — Four-level Initiative → Epic → Story → Task with hierarchical IDs and file-per-item layout.
- [ADR-0003-session-housekeeping-skills.md](./ADR-0003-session-housekeeping-skills.md) — Two project-local Claude Code skills auto-invoked on `Stop`, with a branch+PR-to-master flow that never auto-merges.
