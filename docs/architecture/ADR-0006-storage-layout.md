# ADR-0006 — Storage layout + project-on-disk shape

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-28
**Phase:** scaffolding

## Context

The product needs a persistent substrate that supports:

- **Project / job model (D-011, A-001):** named, async, resumable, durable across app restarts and OS sleep.
- **Project as a versioned artifact (N-003):** every preview is a snapshot, every approve is a publish event, every refine produces a new snapshot. The substrate has to make A-006 (multi-version comparison) and A-003 (publishing audit log) fall out for free.
- **Stable content-hash IDs (A-010):** load-bearing for re-runs and the cross-job cache.
- **Cross-job analysis cache (A-011, N-007):** content-hash + model-version keyed reuse of expensive operations across projects.
- **Failure recovery / resume (A-005):** the orchestrator must be able to restart against a partially-completed job and pick up where it left off.
- **Publishing audit log (A-003):** append-only record per project, per publish event.

Source media is large at MVP scale (1000 photos + 50 videos per D-012, easily tens of GB). Copying it into the project would be wasteful when the user already has it on disk; referencing it (path + content hash) preserves the user's existing organization while still providing a stable identity.

## Decision

**Per-project tree under `~/.impact-crater/`. SQLite for metadata. Source media referenced (path + content hash), not copied. Snapshot directories per N-003. Cross-project content-hash cache. Append-only JSONL audit log.** All paths configurable via the `IMPACT_CRATER_HOME` environment variable for power users.

### Application root and per-project layout

```
~/.impact-crater/
├── db/
│   └── impact-crater.sqlite          # primary metadata store
├── cache/
│   └── {content_hash}/                # cross-project A-011 cache
│       ├── {provider}_{model}_{version}/
│       │   ├── caption.json
│       │   ├── metadata.json
│       │   ├── embedding.npy
│       │   └── ...
│       └── ...
├── audit.jsonl                        # append-only A-003 publish log
└── projects/
    └── {project_id}/
        ├── manifest.json              # project metadata: id, name, brief, settings, created/updated
        ├── sources/
        │   └── {content_hash}.json    # JSON sidecar per source media
        ├── snapshots/
        │   └── {snapshot_id}/         # one dir per render attempt (N-003 substrate)
        │       ├── plan.json          # the curation plan: candidate set, ordering, music alignment
        │       ├── metadata/          # per-asset metadata (links into the cache)
        │       ├── candidates/        # ordered candidate list as the snapshot saw them
        │       ├── render.mp4         # final rendered Story Video (when render-complete)
        │       └── parent.txt         # parent snapshot_id (for refine chains; empty on root snapshot)
        ├── renders/
        │   └── {render_id}.mp4        # symlink (or copy on Windows) to the snapshot's render.mp4
        └── cache/
            └── ...                    # project-local derived artifacts (thumbnails, intermediate frames)
```

### Database schema (SQLite)

Owned by the FastAPI process; accessed via `aiosqlite` for async reads/writes; migrations via Alembic when code lands.

Tables (locked at this ADR; column-level details locked at first feature work):

- `projects` — id, name, brief, created, updated, current_snapshot_id, refine_settings_json
- `media` — content_hash (PK), source_path, ingested_at, media_type, file_size, quick_stats_json
- `project_media` — (project_id, content_hash) — many-to-many; a media item can belong to many projects
- `snapshots` — id, project_id, parent_snapshot_id, created, plan_path, render_path, render_status
- `audit` — id, project_id, snapshot_id, platform, published_at, external_url, response_code, response_summary
- `settings` — key-value (auth tokens by service, routing config overrides per ADR-0007/0009, effort-level user defaults)
- `cache_index` — content_hash, provider, model, model_version, operation, computed_at, cache_path — drives A-011 lookups

### Content-hash convention

- **SHA-256** of the file bytes for source media. Stable, collision-resistant, widely supported.
- Computed once at ingest, stored in the `media` table and the source-sidecar JSON. Re-computed only if the source file is detected changed (mtime mismatch + content-hash recompute).
- Content hash + provider + model + model-version + operation forms the **cache key** for A-011 / N-007.

### Source media handling

- Source media is **referenced, not copied**. The `media.source_path` column holds the absolute path on disk.
- If a path becomes invalid (file moved/deleted), the app falls back to **content-hash search** at re-open: walk the user's known media roots (configurable in `settings`), match by hash, prompt to re-link.
- A "pin to project" feature is deferred (post-MVP) — for users who want project-portable archives, that adds a `pinned` flag and copies to `projects/{project_id}/sources/blobs/{content_hash}.{ext}`.

### Snapshots and refine chains

- Each render attempt produces a new snapshot directory under `snapshots/`.
- Snapshots are **immutable** once written. Refine produces a new snapshot whose `parent.txt` points at the predecessor.
- The chain is the natural data model A-006 (multi-version comparison) consumes when it lands in v1.
- Cleanup policy (deferred to post-MVP): age + count thresholds for trimming old snapshots; the publish event always pins its source snapshot against deletion.

### Audit log

- `~/.impact-crater/audit.jsonl` — append-only, one publish event per line. Schema:
  ```json
  {"timestamp": "2026-04-28T14:23:01Z", "project_id": "...", "snapshot_id": "...", "platform": "youtube", "external_url": "https://youtube.com/watch?v=...", "user_approval_token": "...", "render_content_hash": "..."}
  ```
- The same data is mirrored in the `audit` SQLite table for query convenience. The JSONL file is the authoritative record (an append-only file is harder to corrupt than a database row).
- Out-of-band loss of the JSONL would not break the app but would lose the publish history — backup is the user's responsibility (deferred MVP-lite for an optional cloud-backup feature).

## Alternatives considered

- **Copy source media into the project.** Preserves project portability. Doubles disk usage at MVP scale. Adds a re-ingest step when the user updates a source file (the project's copy stays stale unless re-imported). Rejected — content-hash + path is enough for re-runs; a pin-to-project feature can land post-MVP for users who specifically want archive portability.
- **Postgres or another server-database for metadata.** Adds a deployment dependency end users must provision. SQLite is fast enough for the per-project query patterns and zero-config. Rejected for MVP; the v3 hosted-service mode (config flip per ADR-0005) swaps in Postgres when multi-tenancy demands it.
- **One big "everything" directory (no projects/ subdivision).** Doesn't support N-003 versioning cleanly; fragmenting projects across one directory makes the snapshot graph untenable. Rejected.
- **File-locked JSON-on-disk instead of SQLite.** Doesn't scale to A-011 cache lookups across thousands of content hashes. Rejected.
- **Object-storage-style content-addressed-only layout (no per-project tree).** Treats projects as views into a global blob store. Conceptually clean but over-engineered for desktop-first MVP — users expect "my project lives in a folder" mental model. Rejected for MVP; revisit in v3 hosted mode.
- **Embed cache inside per-project tree (no cross-project cache).** Loses A-011's cross-job reuse, which is one of the seed-list MVP-lite items. Rejected.

## Consequences

- **Source media re-organization on disk by the user breaks the path reference.** The fallback content-hash search at re-open mitigates this and matches industry-standard photo-app behavior (Lightroom / Photos / etc.).
- **Snapshot immutability is a hard rule.** Refine writes a new snapshot, never edits an existing one. The orchestrator's resume-after-failure path (A-005) reads the latest snapshot's `plan.json` to know what's done and what remains.
- **Cache paths are content-hash + provider + model + model-version + operation.** This is exactly the schema N-007 calls for; A-011 reuse falls out automatically. The v1 quality-floor work (A-007) can re-run scoring against a new model_version without invalidating earlier model_version cache entries.
- **The audit log being out-of-band JSONL is intentional.** Append-only file semantics survive crashes better than database transactions if the database file becomes corrupt (rare but possible). The mirrored table makes querying easy.
- **Migration is Alembic-driven.** Database schema migrations land at first feature work; the column-level details inside each table get pinned then.
- **`IMPACT_CRATER_HOME` overrides everything.** Power users running multiple installs (e.g., test vs. prod copy) set the env var; default is `~/.impact-crater/` on every OS (with appropriate Windows / macOS path resolution).
- **Hosted-service mode (v3) replaces per-project filesystem trees with object storage** (S3-class) and SQLite with Postgres. The schema and content-hash convention transfer unchanged; the path resolution layer abstracts disk-vs-object-store. ADR-0006 is intentionally written so that swap is mechanical.

## Linked items

- A-001 (project / job model — this is the substrate), A-003 (publishing audit log — the JSONL file), A-005 (failure recovery — orchestrator reads snapshots), A-010 (stable content-hash IDs — SHA-256 convention), A-011 (cross-job analysis cache — content-hash + model-version keyed), N-003 (project as a versioned artifact — snapshot directories), N-007 (cross-job cache schema — `cache_index` table + cache directory layout), D-011 (job model — async, resumable), D-012 (scale envelope — disk usage assumptions).
- ADR-0005 (process topology — Python process owns these paths).
- Cascades to: ADR-0007 (LLM client cache reads/writes use these paths), ADR-0009 (routing config lives in `~/.impact-crater/config/`), ADR-0011 (curation engine writes to `snapshots/{id}/plan.json`), ADR-0013 (audit-log shape — already pinned here), ADR-0015 (resource accounting — telemetry events live alongside the audit log).
- Decision-log entry: D-024 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md).
- Project task: T-1.3.1.2 in [`project/tasks/`](../../project/tasks/T-1.3.1.2-adr-0006-storage-layout.md).
