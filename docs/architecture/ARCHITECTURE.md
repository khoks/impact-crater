# ARCHITECTURE.md — Impact Crater system architecture

> **Status: rounds 1 + 2 of E-1.3 complete (2026-05-02).** Foundation + LLM stack + media + curation + music alignment locked (ADR-0005..0012 / D-023..D-031). Round 3 (connectors + harness + cross-cutting; ADR-0013..0016) still pending; those sections below retain "to decide" placeholders. Two novel mechanisms surfaced in round 2 are filed in [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md): N-008 (vision-LLM face recognition via labeled reference collage) and N-009 (agentic refinement with custom plan generation).

The accepted decisions live in this folder as `ADR-NNNN-*.md` files. As of 2026-05-02: twelve ADRs accepted (license, work-tracking, skills, auto-merge policy, process topology + language stack, storage layout, remote-LLM abstraction, local-LLM runtime slot, cost-tiered per-operation lineup, media pipeline framework, curation engine algorithm, music alignment strategy); four still open and to be filed in round 3 of E-1.3.

---

## Component map

The eventual diagram covers, at minimum, these layers:

1. **Client / UI** — where the user uploads media, types the brief, reviews previews, and approves publishes. **TypeScript + React** served from the FastAPI process per [ADR-0005](./ADR-0005-process-topology-language-stack.md).
2. **Project & media library** — the persistent store of the user's source media, organized by project. **Per-project tree under `~/.impact-crater/projects/{project_id}/` with SQLite metadata, content-hash-referenced source media, snapshot directories per N-003** per [ADR-0006](./ADR-0006-storage-layout.md).
3. **Analysis pipeline** — the path from raw media to per-asset metadata: Pillow + pillow-heif (HEIC) + rawpy (RAW) for photo decode; ffmpeg-python for video decode; imagehash (pHash + dHash) for perceptual hashing; PySceneDetect for scene segmentation; vision-LLM (per ADR-0007/0009 Tier-M) for face detection + rich metadata extraction (D-009); **person library + reference-collage face recognition** (N-008) augmenting the metadata stage. See [ADR-0010](./ADR-0010-media-pipeline-framework.md).
4. **Curation engine** — the 9-stage pipeline from per-asset metadata to a rendered Story Video. Stages: ingest → bulk per-asset ops → rich metadata → pre-filter (floor + ≤80% ceiling) → narrative-arc judgment (N-001, Tier-L Opus) → plan compilation + orchestrator second-guess (with user reconfirm) → render → preview → agentic refinement (N-009, Tier-M tool-call loop). See [ADR-0011](./ADR-0011-curation-engine-algorithm.md).
5. **Render pipeline** — in-process ffmpeg subprocesses spawned by the orchestrator's worker pool; H.264/yuv420p/AAC at YouTube-friendly defaults; smart-crop via `smartcrop.py` with face-bbox bias; aspect-ratio at MVP = 16:9 only (YouTube). Music alignment (beat-grid, section-to-media NL mapping per A-013, agentic duration handling) sits inside this layer. See [ADR-0010](./ADR-0010-media-pipeline-framework.md) (render execution) + [ADR-0012](./ADR-0012-music-alignment-strategy.md) (music alignment).
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

## Media pipeline

Locked in [ADR-0010](./ADR-0010-media-pipeline-framework.md). Summary:

- **Photo decode:** Pillow + pillow-heif (HEIC, iPhone-default) + rawpy (RAW: CR2/NEF/ARW/DNG/RAF/ORF/RW2). Working colorspace at metadata extraction = sRGB.
- **Video decode:** ffmpeg via `ffmpeg-python`; ffprobe at ingest. No re-encode at analysis — scene-representative frames extracted as PNG.
- **Thumbnails:** 256 + 1024 px JPEG cached at ingest.
- **Perceptual hash:** `imagehash` library with both pHash + dHash; per-video scenes hashed at start/middle/end.
- **Dedup posture:** off by default; surface as suggestion; user explicitly opts in per cluster.
- **Face detection + recognition:** vision-LLM only at MVP (no separate face-recognition library). The novel **person-library + reference-collage** mechanism (N-008) builds a per-person library of N face photos (default 5) and constructs a labeled reference collage at recognition time as a second image input to `extract_metadata_image`; structured-output schema gains `recognized_persons` field with confidence scores. Cache key includes `library_version_hash` for correct invalidation.
- **Scene segmentation:** PySceneDetect `ContentDetector`; 50/video cap; 3 representative frames per scene.
- **Smart-crop:** `smartcrop.py` saliency CNN with face-bbox bias; center-crop fallback.
- **Aspect ratios at MVP:** 16:9 only (YouTube per D-007); pad-or-letterbox for 9:16 sources.
- **Render execution:** in-process ffmpeg subprocesses via the orchestrator's worker pool; max 1 concurrent render at MVP.
- **Worker pool:** asyncio task pool with cpu/ffmpeg/network worker classes; backpressure via job-progress websocket; cancellation via `JobCancelled`; resume via snapshot `plan.json`.

---

## Curation engine

Locked in [ADR-0011](./ADR-0011-curation-engine-algorithm.md). The 9-stage pipeline:

1. **Ingest + content-hash + scene-segment + thumbnails** (deterministic, ADR-0010).
2. **Bulk per-asset ops:** embed + caption + score (Tier-S Gemini Flash + Google embeddings per ADR-0009).
3. **Rich metadata extraction** (Tier-M Sonnet 4.7) with the D-009 schema; augmented with `recognized_persons` from N-008 when the person library is non-empty.
4. **Pre-filter** (deterministic): quality floor + dedup-grouping + time/location clustering → candidate set sized to `clamp(input × 30%, floor, ceiling)` where `floor = max(50, target_duration_seconds × 2)` and `ceiling = floor(input_count × 0.80)`. User-overridable via effort-level UX, hard-capped within `[floor, ceiling]`.
5. **Narrative-arc judgment** (N-001, Tier-L Opus, **single call per job**) producing structured `ArcJudgment` with selected items + ordering + section-to-media mapping (for music-video mode per A-013) + arc reasoning.
6. **Plan compilation + orchestrator second-guess** (deterministic + Tier-M). The orchestrator runs a sanity-check pass; if it disagrees with the judge AND confidence > 0.6, **surfaces proposed overrides to the user** via websocket; user picks Apply/Skip/Modify-with-NL per override before render proceeds.
7. **Render** (deterministic, ffmpeg) executes the finalized plan; H.264/yuv420p/AAC; two-pass loudness normalization at -16 LUFS.
8. **Preview UI** with twin Approve / Refine actions per D-022.
9. **Agentic refinement** (N-009, Tier-M tool-call loop, bounded at 10 turns). The orchestrator's thinking step chooses among 5 strategies — partial-fix-via-plan-edit / partial-fix-via-stage-3-rerun / full-reprocess / request-additional-input / explain-why-not-possible — based on user's NL message + project context + available tools. Per-snapshot persistence of the chosen plan + reasoning.

**Cache reuse story** (per A-011 / N-007): Stages 1–3 typically cached on re-run + on refine; Stage 5 always re-runs on refine (refinement message changes input); Stages 6–7 always re-run. Typical refinement cost ~$1–5 USD vs ~$7–22 for a full job per ADR-0009.

---

## Music alignment

Locked in [ADR-0012](./ADR-0012-music-alignment-strategy.md). Summary:

- **Audio ingest:** ffmpeg → 22050 Hz mono WAV for analysis.
- **Music structure analysis:** Madmom (RNN-based beat + downbeat detection — state-of-the-art for music-video cuts) + librosa (sections via `librosa.segment.agglomerative` + RMS energy curve via `librosa.feature.rms`). `MusicAnalyzer` abstraction makes the libraries swappable; MVP implements `MadmomLibrosaAnalyzer`.
- **Beat-grid generation:** default cut every 4 beats (1 bar at 4/4); tempo-adjusted for slow / fast tempos; section-boundary snapping within 200ms; user-overridable via effort-level UX.
- **Section-to-media NL mapping (A-013, full version in MVP per D-031):** the user's free-text spec ("intro = scenic, chorus = summit") passes verbatim to Stage 5 narrative judge alongside brief + music structure. No structured-parse stage; the Tier-L Opus judge handles the prose natively.
- **Music duration mismatch handling = agentic** (Tier-M tool call): orchestrator picks `fade_out` / `loop_with_crossfade` / `truncate_at_section` / `loop_then_truncate` based on section boundaries, loopability, target deviation. Strategy + rationale recorded on snapshot and surfaced via cost-transparency UI.
- **Render-time alignment:** standard mode = audio under entire video at -16 LUFS; music-video mode = cuts snap to `CutGrid.cut_points_ms`; two-pass `loudnorm` for YouTube-friendly loudness on both modes.

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

## Accepted ADRs (as of E-1.3 round 2, 2026-05-02)

- [ADR-0001-license.md](./ADR-0001-license.md) — Business Source License 1.1 with Change Date 2030-04-25.
- [ADR-0002-work-tracking-hierarchy.md](./ADR-0002-work-tracking-hierarchy.md) — Four-level Initiative → Epic → Story → Task with hierarchical IDs and file-per-item layout.
- [ADR-0003-session-housekeeping-skills.md](./ADR-0003-session-housekeeping-skills.md) — Two project-local Claude Code skills auto-invoked on `Stop`, with a branch+PR-to-master flow. ("Never auto-merge" clause superseded by ADR-0004.)
- [ADR-0004-skill-pr-auto-merge.md](./ADR-0004-skill-pr-auto-merge.md) — All Claude-generated PRs auto-merge with `gh pr merge --squash --delete-branch --admin`.
- [ADR-0005-process-topology-language-stack.md](./ADR-0005-process-topology-language-stack.md) — Backend = Python 3.11+ / FastAPI; frontend = TypeScript + React; subprocess workers for heavy lifting; `pip install impact-crater` packaging.
- [ADR-0006-storage-layout.md](./ADR-0006-storage-layout.md) — Per-project tree under `~/.impact-crater/projects/`; SQLite for metadata; source media referenced (path + SHA-256); snapshot directories per N-003; cross-project content-hash cache; append-only JSONL audit log.
- [ADR-0007-remote-llm-abstraction.md](./ADR-0007-remote-llm-abstraction.md) — `LLMClient` Python protocol with typed async methods per operation; MVP provider list = Anthropic + Google; static YAML routing dispatch (the v1 N-002 router replaces this with an agentic resolver).
- [ADR-0008-local-llm-runtime-slot.md](./ADR-0008-local-llm-runtime-slot.md) — `LocalLLMClient` slot in the same registry; MVP ships an empty stub; v1 candidate runtime = Ollama; ≤32B parameter cap enforced at model-load time.
- [ADR-0009-cost-tiered-model-lineup.md](./ADR-0009-cost-tiered-model-lineup.md) — Three cost tiers (S = Gemini 2.5 Flash, M = Claude Sonnet 4.7, L = Claude Opus 4.7); per-operation static routing table assigning every operation to a tier; Tier-L reserved for the one-call-per-job N-001 narrative-arc judgment.
- [ADR-0010-media-pipeline-framework.md](./ADR-0010-media-pipeline-framework.md) — Pillow + pillow-heif + rawpy for photo decode; ffmpeg-python for video; imagehash (pHash + dHash); PySceneDetect; smartcrop.py; vision-LLM-only face stack with **person-library + reference-collage recognition (N-008)**; in-process ffmpeg render with max-1-concurrency at MVP.
- [ADR-0011-curation-engine-algorithm.md](./ADR-0011-curation-engine-algorithm.md) — 9-stage pipeline: ingest → bulk per-asset ops (Tier-S + embed) → rich metadata (Tier-M) → pre-filter (floor + ≤80% ceiling) → narrative-arc judgment (N-001, Tier-L Opus) → plan compile + orchestrator second-guess with user reconfirm → render → preview → **agentic refinement (N-009, Tier-M tool-call loop)**.
- [ADR-0012-music-alignment-strategy.md](./ADR-0012-music-alignment-strategy.md) — Madmom (beats) + librosa (sections + energy); tempo-aware beat-grid; **section-to-media NL mapping in MVP (A-013, full version per D-031)** passed verbatim to Stage 5; agentic music-duration mismatch handling via Tier-M tool call; two-pass `loudnorm` for YouTube-friendly loudness.

## Pending ADRs (round 3 of E-1.3)

- ADR-0013 — Connector layer credential model + audit-log shape (YouTube only at MVP per D-007). *Round 3.*
- ADR-0014 — Agent harness topology (formalize D-017 single orchestrator with concrete tool surface, including tools introduced in round 2: `analyze_music_duration_mismatch`, `re_run_stage_5_with_addendum`, `re_extract_metadata_for`, `re_run_pre_filter_with_overrides`, `request_user_input`, `explain_why_not_possible`, `orchestrator_second_guess`). *Round 3.*
- ADR-0015 — Resource accounting + quota model (formalize D-013 + A-004 + A-015 telemetry schema; consumes the `LLMCallEvent` stream from ADR-0007 + the per-stage cost from ADR-0011). *Round 3.*
- ADR-0016 — Privacy posture defaults (formalize A-002 + D-016 user-facing flow; person-library + face-blur interactions per ADR-0010). *Round 3.*
