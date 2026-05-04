-- 001_init.sql — Impact Crater initial schema.
--
-- Sources:
--   ADR-0006 storage layout (projects, media, project_media, snapshots,
--                            audit, settings, cache_index)
--   ADR-0010 / N-008 person library (persons, person_face_photos)
--   ADR-0013 connector layer (connector_credentials)
--   ADR-0015 resource accounting (quota_state)
--
-- Column-level details are intentionally lean at M0; later milestones
-- add columns (or new tables) via separate migrations rather than
-- altering this file.

-- -----------------------------------------------------------------------
-- settings — generic key/value store. Used by the first-time-setup wizard
-- (S-2.1.5) and by any future feature that needs simple persisted state.
-- The `encrypted` flag tells callers whether the value is Fernet-ciphertext.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    encrypted  INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------
-- projects — one row per user-created project.
-- ADR-0006 §"Database schema (SQLite)".
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    brief                 TEXT,
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_snapshot_id   TEXT,
    refine_settings_json  TEXT
);

-- -----------------------------------------------------------------------
-- media — content-addressed source media records.
-- ADR-0006 + A-010 (stable content-hash IDs) + A-011 (cross-job cache).
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media (
    content_hash    TEXT PRIMARY KEY,            -- SHA-256 of file bytes
    source_path     TEXT NOT NULL,
    ingested_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    media_type      TEXT NOT NULL,               -- 'photo' / 'video' / 'audio'
    file_size       INTEGER,
    quick_stats_json TEXT
);

-- -----------------------------------------------------------------------
-- project_media — many-to-many between projects and media. A media item
-- can belong to multiple projects (cross-job cache reuse depends on this).
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_media (
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_hash  TEXT NOT NULL REFERENCES media(content_hash) ON DELETE CASCADE,
    added_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, content_hash)
);

-- -----------------------------------------------------------------------
-- snapshots — N-003 substrate. Each render attempt produces an immutable
-- snapshot directory; `parent_snapshot_id` builds the refinement chain
-- (per ADR-0011 Stage 9 / N-009 + ADR-0014 N-010).
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS snapshots (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_snapshot_id  TEXT REFERENCES snapshots(id),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    plan_path           TEXT,
    render_path         TEXT,
    render_status       TEXT NOT NULL DEFAULT 'pending'  -- pending/in_progress/success/failure/cancelled
);
CREATE INDEX IF NOT EXISTS snapshots_project_idx
    ON snapshots(project_id);

-- -----------------------------------------------------------------------
-- audit — A-003 publishing audit log. Mirrored from the append-only
-- JSONL at ~/.impact-crater/audit.jsonl per ADR-0006 / ADR-0013.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_version       INTEGER NOT NULL DEFAULT 1,
    project_id           TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_id          TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    platform             TEXT NOT NULL,                -- 'youtube' / 'instagram' / etc.
    external_id          TEXT,                          -- platform's video / post id
    external_url         TEXT,
    response_code        INTEGER,
    response_summary     TEXT,
    render_content_hash  TEXT,
    user_approval_token  TEXT,
    publish_metadata     TEXT,                          -- JSON
    description_full     TEXT,
    published_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS audit_project_idx
    ON audit(project_id, published_at);

-- -----------------------------------------------------------------------
-- cache_index — A-011 / N-007 cross-project LLM cache.
-- Cache key = sha256(content_hash + provider + model + model_version
--                    + operation + prompt_version + params_canonical).
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cache_index (
    cache_key       TEXT PRIMARY KEY,
    content_hash    TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    operation       TEXT NOT NULL,
    prompt_version  TEXT,
    params_canonical TEXT,
    cache_path      TEXT NOT NULL,
    privacy_class   TEXT,                              -- ADR-0016 N-011 — face_data / visual_only / derived_metadata / text_only
    library_version_hash TEXT,                          -- ADR-0010 / N-008 — invalidates on person-library change
    computed_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS cache_index_lookup_idx
    ON cache_index(content_hash, operation, provider, model);

-- -----------------------------------------------------------------------
-- connector_credentials — ADR-0013. Tokens encrypted at rest with the
-- Fernet key at ~/.impact-crater/db/.fernet-key.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS connector_credentials (
    connector_name  TEXT NOT NULL,                     -- 'youtube' / 'instagram' / etc.
    user_handle     TEXT NOT NULL,                     -- platform's canonical user id
    access_token    TEXT NOT NULL,                     -- Fernet ciphertext
    refresh_token   TEXT,                              -- Fernet ciphertext
    expires_at      INTEGER NOT NULL,                  -- UNIX epoch seconds
    scopes_granted  TEXT NOT NULL,                     -- comma-separated
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (connector_name, user_handle)
);

-- -----------------------------------------------------------------------
-- quota_state — ADR-0015 dual-cap quota tracking.
-- One row per (date, provider). The `_total_` provider aggregates all
-- providers for fast total-cap checks.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quota_state (
    date          TEXT NOT NULL,                       -- ISO date YYYY-MM-DD
    provider      TEXT NOT NULL,                       -- 'anthropic' / 'google' / 'local' / '_total_'
    spent_usd     REAL NOT NULL DEFAULT 0,
    last_updated  INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
    PRIMARY KEY (date, provider)
);

-- -----------------------------------------------------------------------
-- persons — ADR-0010 / N-008 person library (display names + notes).
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS persons (
    id            TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------
-- person_face_photos — ADR-0010 / N-008 — N face photos per person
-- (default 5; range 3-10) for the labeled reference-collage builder.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_face_photos (
    id              TEXT PRIMARY KEY,
    person_id       TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    content_hash    TEXT NOT NULL,                     -- of the source photo
    face_crop_bbox  TEXT NOT NULL,                     -- JSON [x, y, w, h]
    captured_at     TEXT,
    is_primary      INTEGER NOT NULL DEFAULT 0,
    added_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS person_face_photos_person_idx
    ON person_face_photos(person_id);
