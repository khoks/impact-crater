-- 008: durable job registry (S-2.9.19).
--
-- The in-memory JobRegistry saves each job's JobSnapshot here on every state
-- and stage change, so a finished job's progress and preview pages survive a
-- server restart, and a job a restart cut off is reported as interrupted
-- instead of vanishing.
CREATE TABLE IF NOT EXISTS jobs (
    job_id        TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL,
    state         TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    submitted_at  TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state_idx ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_submitted_idx ON jobs(submitted_at);
