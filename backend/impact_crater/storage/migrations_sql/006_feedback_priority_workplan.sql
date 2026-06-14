-- Dev tracker pages (A-024).
--
-- 1. Feedback items get an editable priority so the feedback-tracker page
--    can rank what to act on first (status already exists).
-- 2. workplan_overrides lets the workplan-tracker page change an item's
--    priority without writing to the project/ markdown (which is the
--    work-tracker skill's domain + goes through PRs). The override is the
--    source the page displays and what a later session reconciles into the
--    canonical markdown.

ALTER TABLE feedback ADD COLUMN priority TEXT NOT NULL DEFAULT 'P2';  -- P0|P1|P2|P3

CREATE TABLE IF NOT EXISTS workplan_overrides (
    item_id     TEXT PRIMARY KEY,   -- I-2 / E-2.9 / S-2.9.8 / T-...
    priority    TEXT,               -- P0|P1|P2|P3 (NULL = no override)
    note        TEXT,               -- optional developer note
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
