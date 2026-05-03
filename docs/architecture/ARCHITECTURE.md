# ARCHITECTURE.md — Impact Crater system architecture

> **Status: E-1.3 complete (2026-05-03).** All 12 ADRs from rounds 1 + 2 + 3 accepted (ADR-0005..0016 / D-023..D-035). Plus the four governance ADRs (ADR-0001..0004) gives 16 ADRs total. Eleven novel mechanisms (N-001..N-011) filed in [`docs/vision/NOVEL_IDEAS.md`](../vision/NOVEL_IDEAS.md). E-1.4 (roadmap + MVP final lock) is the next thing on the board.

The accepted decisions live in this folder as `ADR-NNNN-*.md` files. As of 2026-05-03: sixteen ADRs accepted, no remaining "to decide" placeholders in this document.

---

## Component map

The eventual diagram covers, at minimum, these layers:

1. **Client / UI** — where the user uploads media, types the brief, reviews previews, and approves publishes. **TypeScript + React** served from the FastAPI process per [ADR-0005](./ADR-0005-process-topology-language-stack.md).
2. **Project & media library** — the persistent store of the user's source media, organized by project. **Per-project tree under `~/.impact-crater/projects/{project_id}/` with SQLite metadata, content-hash-referenced source media, snapshot directories per N-003** per [ADR-0006](./ADR-0006-storage-layout.md).
3. **Analysis pipeline** — the path from raw media to per-asset metadata: Pillow + pillow-heif (HEIC) + rawpy (RAW) for photo decode; ffmpeg-python for video decode; imagehash (pHash + dHash) for perceptual hashing; PySceneDetect for scene segmentation; vision-LLM (per ADR-0007/0009 Tier-M) for face detection + rich metadata extraction (D-009); **person library + reference-collage face recognition** (N-008) augmenting the metadata stage. See [ADR-0010](./ADR-0010-media-pipeline-framework.md).
4. **Curation engine** — the 9-stage pipeline from per-asset metadata to a rendered Story Video. Stages: ingest → bulk per-asset ops → rich metadata → pre-filter (floor + ≤80% ceiling) → narrative-arc judgment (N-001, Tier-L Opus) → plan compilation + orchestrator second-guess (with user reconfirm) → render → preview → agentic refinement (N-009, Tier-M tool-call loop). See [ADR-0011](./ADR-0011-curation-engine-algorithm.md).
5. **Render pipeline** — in-process ffmpeg subprocesses spawned by the orchestrator's worker pool; H.264/yuv420p/AAC at YouTube-friendly defaults; smart-crop via `smartcrop.py` with face-bbox bias; aspect-ratio at MVP = 16:9 only (YouTube). Music alignment (beat-grid, section-to-media NL mapping per A-013, agentic duration handling) sits inside this layer. See [ADR-0010](./ADR-0010-media-pipeline-framework.md) (render execution) + [ADR-0012](./ADR-0012-music-alignment-strategy.md) (music alignment).
6. **Agent harness** — single `Orchestrator` on Tier-M Sonnet 4.7 with a consolidated tool surface (LLM ops + pipeline + refinement + music + connector + person-library + profile tools). Reasoning model = tool-call loop bounded at 50 turns/session; failure-mode UX = continue / abandon / restart. **Cross-project user profile (N-010)** persisted at `~/.impact-crater/profile/` provides agentic learning across the user's lifetime use of the product. See [ADR-0014](./ADR-0014-agent-harness-topology.md).
7. **LLM client + router** — every LLM call goes through the **`LLMClient` Python protocol** with provider implementations behind it (Anthropic + Google at MVP) and a **routing dispatch** mapping operations to providers/models per [ADR-0007](./ADR-0007-remote-llm-abstraction.md), [ADR-0008](./ADR-0008-local-llm-runtime-slot.md) (local slot, architecture-only at MVP), [ADR-0009](./ADR-0009-cost-tiered-model-lineup.md) (per-op cost-tiered lineup). **Privacy-sensitive routing extension (N-011)** layers per-operation `privacy_class` + per-provider `eligibility_for_class` on top of the static cost-tiered dispatch — face-data ops route to local LLM only when blur-faces is ON. See [ADR-0016](./ADR-0016-privacy-posture-defaults.md).
8. **Connector layer** — `Connector` Python protocol for publish targets; `YouTubeConnector` MVP impl uses OAuth 2.0 + resumable `videos.insert` with 256 MB chunks; default video privacy on upload = public, user picks per upload via the publish UI; tokens stored in SQLite with Fernet encryption. Audit-log entry shape finalized. See [ADR-0013](./ADR-0013-connector-layer.md).
9. **Resource accounting + cost-transparency** — append-only telemetry JSONL at `~/.impact-crater/telemetry.jsonl` with `LLMCallEvent` / `RenderEvent` / `IngestEvent` / `OrchestratorTurnEvent` / `JobLifecycleEvent`; `JobCostSummary` per snapshot; rate cards as YAML; **dual-cap quota** (total + per-provider, both hard) configured during first-time setup, no system default. See [ADR-0015](./ADR-0015-resource-accounting.md).
10. **Profile / theme store** — *partly here at MVP via N-010 cross-project profile (style preferences + orchestrator priors + narrative patterns derived from a feedback log).* The reference-media style learning (A-014) — uploaded media / public URLs / prior projects as inspiration sources — remains v1 work. See [ADR-0014](./ADR-0014-agent-harness-topology.md) §"Cross-project user profile."

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

## Connectors

Locked in [ADR-0013](./ADR-0013-connector-layer.md). Summary:

- **Connector protocol:** `Connector` Python protocol with `authenticate / is_authenticated / revoke_credentials / validate_artifact / upload`. v1 platforms (Instagram / Facebook / X) plug in as new implementations.
- **YouTube at MVP:** `YouTubeConnector` using `google-auth-oauthlib` + `google-api-python-client`; OAuth via local-loopback callback; YouTube Data API v3 `videos.insert` resumable upload, 256 MB chunks; progress streamed to the FastAPI websocket per ADR-0005.
- **Default video privacy on upload = `public`** (per round-3 Q1); user picks visibility (private / unlisted / public) explicitly per upload via the publish UI; the explicit Approve gate (D-020) is the safety net. Approve button shows the selected visibility one more time before clicking.
- **Token storage = all in SQLite** (per round-3 Q2): `connector_credentials` table (extension to ADR-0006); `access_token` + `refresh_token` Fernet-encrypted at rest with key at `~/.impact-crater/db/.fernet-key` (0600 perms). Token refresh as a background task before every connector call.
- **API rejection model:** structured `ConnectorError` hierarchy (`ConnectorValidationError`, `ConnectorUploadError`, `ConnectorAuthError`) with `user_actionable` + `suggested_action`. YouTube error mapping table specified.
- **Audit-log entry shape (final):** JSONL line + SQLite `audit` mirror per ADR-0006; fields = schema_version + timestamp + project/snapshot IDs + platform + external_id/url + response_code/summary + render_content_hash + opaque in-session `user_approval_token` + `publish_metadata` (title + truncated-description + visibility + tags_count + scheduled_publish_at).

---

## Agent harness

Locked in [ADR-0014](./ADR-0014-agent-harness-topology.md). Summary:

- **Single `Orchestrator` class** running on Tier-M Sonnet 4.7 (per ADR-0009 `orchestrator_reasoning`). Multi-agent (planner + media-analyst + editor + publisher) deferred to v2 per D-017.
- **Tool registry** with per-tool `idempotency_class` (`free` / `project_mutating` / `external_side_effect`). External-side-effect tools (publish-to-platform) require explicit user confirmation per call.
- **Consolidated tool surface** (rounds 1 + 2 + 3): LLM operations (per ADR-0007) + pipeline tools (`ingest_media`, `compute_perceptual_hashes`, `segment_video_scenes`, `compute_dedup_clusters`, `pre_filter_candidates`, `compile_render_plan`, `orchestrator_second_guess`, `execute_render`) + refinement tools (`re_run_stage_5_with_addendum`, `re_extract_metadata_for`, `re_run_pre_filter_with_overrides`, `request_user_input`, `explain_why_not_possible`) + music tools (`analyze_music`, `analyze_music_duration_mismatch`) + connector tools (`validate_publish_artifact`, `upload_to_platform`, `record_audit_event`) + person-library tools (`add_person`, `add_face_photo`, `build_reference_collage`, `remove_person`) + profile tools (`read_user_profile`, `suggest_from_profile`, `record_feedback_event`, `derive_profile_priors`).
- **Reasoning model:** tool-call loop bounded at 50 turns per orchestration session (refinement subloop has its own 10-turn bound per ADR-0011 Stage 9 / N-009).
- **Failure-mode UX:** three actions when stuck — **continue** (more context; reset turn budget), **abandon** (mark snapshot failed), **restart** (start fresh from Stage 4). Manual override deferred to v1.
- **Cancellation + resume:** `JobCancelled` propagates through tool-call loop and worker pool (per ADR-0010); on startup, FastAPI scans for `in_progress` snapshots and surfaces "Resume?" prompts.
- **Cross-project user profile (N-010, novel mechanism):** persistent profile at `~/.impact-crater/profile/profile.json` derived from an append-only `feedback_log.jsonl` via Tier-M re-derivation; six pipeline-stage read sites (job creation, brief parsing, Stage 4 quality floor, Stage 5 narrative-arc context, Stage 6 second-guess threshold, Stage 9 refinement strategy bias). Bounded re-derivation cadence (incremental N=10, full N=100). One-click reset.

---

## Cross-cutting concerns

- **Resource accounting.** Locked in [ADR-0015](./ADR-0015-resource-accounting.md). Append-only telemetry JSONL with five event types; per-job `JobCostSummary`; YAML rate cards versioned per `model_version`; **dual-cap quota** (total + per-provider, both hard) configured during first-time-setup wizard, no system default; pre-job + per-stage check; mid-job pause-and-prompt on cap-approach.
- **Privacy posture.** Locked in [ADR-0016](./ADR-0016-privacy-posture-defaults.md). Three project-level toggles (strip-EXIF default ON, strip-GPS-only default ON, blur-faces default OFF); toggle interaction matrix documented; one face-detection-only library for blur masking (the only deterministic-face-detection dep). **Privacy-sensitive routing extension (N-011, novel mechanism):** per-operation `privacy_class` + per-provider `eligibility_for_class` extends ADR-0007 routing config; `face_data`-class ops route to local LLM only when blur-faces is ON; graceful-degradation path when no eligible provider. Plug-and-play hook in MVP; functional in v1 when the local-LLM runtime lands.
- **Reproducibility.** Re-running curation on the same project gives a stable result via the content-hash + model-version cache (ADR-0006 + N-007); LLM stochasticity controlled via per-operation temperature settings.
- **Cancellation.** `JobCancelled` propagates through the worker pool (ADR-0010) and the orchestrator's tool-call loop (ADR-0014); ffmpeg subprocesses get SIGTERM with grace then SIGKILL.
- **Telemetry.** Local-only at MVP per ADR-0015; opt-in remote share is a v1 consideration.

---

## Accepted ADRs (E-1.3 complete, 2026-05-03)

**Governance (ADR-0001..0004):**

- [ADR-0001-license.md](./ADR-0001-license.md) — Business Source License 1.1 with Change Date 2030-04-25.
- [ADR-0002-work-tracking-hierarchy.md](./ADR-0002-work-tracking-hierarchy.md) — Four-level Initiative → Epic → Story → Task with hierarchical IDs and file-per-item layout.
- [ADR-0003-session-housekeeping-skills.md](./ADR-0003-session-housekeeping-skills.md) — Two project-local Claude Code skills auto-invoked on `Stop`, with a branch+PR-to-master flow. ("Never auto-merge" clause superseded by ADR-0004.)
- [ADR-0004-skill-pr-auto-merge.md](./ADR-0004-skill-pr-auto-merge.md) — All Claude-generated PRs auto-merge with `gh pr merge --squash --delete-branch --admin`.

**Foundation + LLM stack (ADR-0005..0009; E-1.3 round 1):**

- [ADR-0005-process-topology-language-stack.md](./ADR-0005-process-topology-language-stack.md) — Backend = Python 3.11+ / FastAPI; frontend = TypeScript + React; subprocess workers for heavy lifting; `pip install impact-crater` packaging.
- [ADR-0006-storage-layout.md](./ADR-0006-storage-layout.md) — Per-project tree under `~/.impact-crater/projects/`; SQLite for metadata; source media referenced (path + SHA-256); snapshot directories per N-003; cross-project content-hash cache; append-only JSONL audit log.
- [ADR-0007-remote-llm-abstraction.md](./ADR-0007-remote-llm-abstraction.md) — `LLMClient` Python protocol with typed async methods per operation; MVP provider list = Anthropic + Google; static YAML routing dispatch (the v1 N-002 router replaces this with an agentic resolver; ADR-0016 extends with privacy-class + eligibility).
- [ADR-0008-local-llm-runtime-slot.md](./ADR-0008-local-llm-runtime-slot.md) — `LocalLLMClient` slot in the same registry; MVP ships an empty stub; v1 candidate runtime = Ollama; ≤32B parameter cap enforced at model-load time.
- [ADR-0009-cost-tiered-model-lineup.md](./ADR-0009-cost-tiered-model-lineup.md) — Three cost tiers (S = Gemini 2.5 Flash, M = Claude Sonnet 4.7, L = Claude Opus 4.7); per-operation static routing table; Tier-L reserved for the one-call-per-job N-001 narrative-arc judgment.

**Media + curation (ADR-0010..0012; E-1.3 round 2):**

- [ADR-0010-media-pipeline-framework.md](./ADR-0010-media-pipeline-framework.md) — Pillow + pillow-heif + rawpy for photo decode; ffmpeg-python for video; imagehash (pHash + dHash); PySceneDetect; smartcrop.py; vision-LLM-only face stack with **person-library + reference-collage recognition (N-008)**; in-process ffmpeg render with max-1-concurrency at MVP.
- [ADR-0011-curation-engine-algorithm.md](./ADR-0011-curation-engine-algorithm.md) — 9-stage pipeline: ingest → bulk per-asset ops (Tier-S + embed) → rich metadata (Tier-M) → pre-filter (floor + ≤80% ceiling) → narrative-arc judgment (N-001, Tier-L Opus) → plan compile + orchestrator second-guess with user reconfirm → render → preview → **agentic refinement (N-009, Tier-M tool-call loop)**.
- [ADR-0012-music-alignment-strategy.md](./ADR-0012-music-alignment-strategy.md) — Madmom (beats) + librosa (sections + energy); tempo-aware beat-grid; **section-to-media NL mapping in MVP (A-013, full version per D-031)** passed verbatim to Stage 5; agentic music-duration mismatch handling via Tier-M tool call; two-pass `loudnorm` for YouTube-friendly loudness.

**Connectors + harness + cross-cutting (ADR-0013..0016; E-1.3 round 3):**

- [ADR-0013-connector-layer.md](./ADR-0013-connector-layer.md) — `Connector` Python protocol; `YouTubeConnector` MVP impl with OAuth + resumable `videos.insert` (256 MB chunks); **default video privacy on upload = public, user picks per upload via the publish UI**; tokens in SQLite Fernet-encrypted; structured `ConnectorError` hierarchy; finalized audit-entry schema.
- [ADR-0014-agent-harness-topology.md](./ADR-0014-agent-harness-topology.md) — Single `Orchestrator` on Tier-M Sonnet 4.7; consolidated tool surface with per-tool `idempotency_class`; tool-call loop bounded at 50 turns/session; failure-mode UX = continue / abandon / restart. **Cross-project user profile (N-010, novel mechanism):** persistent profile derived from a feedback log via Tier-M re-derivation; read at six pipeline stages; one-click reset.
- [ADR-0015-resource-accounting.md](./ADR-0015-resource-accounting.md) — Append-only telemetry JSONL with five event types; per-job `JobCostSummary`; YAML rate cards versioned per `model_version`; **dual-cap quota (total + per-provider, both hard)** configured during first-time-setup, no system default; pre-job + per-stage check; mid-job pause-and-prompt on cap-approach.
- [ADR-0016-privacy-posture-defaults.md](./ADR-0016-privacy-posture-defaults.md) — Three project-level toggles (strip-EXIF default ON, strip-GPS-only default ON, blur-faces default OFF); one face-detection-only library for blur masking; toggle interaction matrix documented. **Privacy-sensitive routing extension (N-011, novel mechanism):** per-operation `privacy_class` + per-provider `eligibility_for_class` layer on top of ADR-0007 routing; face-data ops route to local LLM only when blur-faces is ON; graceful-degradation path. Plug-and-play hook in MVP; functional in v1 when local-LLM lands.

**No pending ADRs.** E-1.3 closed 2026-05-03.
