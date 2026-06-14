-- User feedback on pipeline decisions (A-023 feedback loop).
--
-- One row per piece of feedback the user gives in the in-app diagnostics
-- viewer: a verdict (correct / incorrect / different) on a specific phase
-- decision, optionally tied to a specific media item, plus a free-text
-- note and a snapshot of the decision's context. `status` lets a future
-- session (or the user) mark feedback as triaged / addressed after Claude
-- acts on it. The append-only ~/.impact-crater/feedback.jsonl mirror is
-- written alongside for easy out-of-band consumption.

CREATE TABLE IF NOT EXISTS feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    job_id         TEXT,
    project_id     TEXT,
    snapshot_id    TEXT,
    phase          TEXT NOT NULL,             -- stage_4_prefilter / stage_5_judge / ...
    decision_ref   TEXT,                       -- e.g. "drop:semantic_duplicate" / "select:peak" / person_id
    content_hash   TEXT,                       -- the media this is about, if any
    verdict        TEXT NOT NULL,              -- "correct" | "incorrect" | "different"
    comment        TEXT,                       -- the user's free-text input
    context_json   TEXT,                       -- snapshot of the decision the UI showed
    status         TEXT NOT NULL DEFAULT 'new' -- new | triaged | addressed | dismissed
);

CREATE INDEX IF NOT EXISTS feedback_status_idx ON feedback(status, created_at);
CREATE INDEX IF NOT EXISTS feedback_snapshot_idx ON feedback(snapshot_id);
