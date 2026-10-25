-- 007: triage bookkeeping for the A-023 feedback loop (S-2.13.3).
--
-- `scripts/feedback.py mark <id> <status> --note "..."` records WHY an item
-- left `new` (the story / PR that addressed it, or the follow-up that will)
-- and WHEN. The SQLite `feedback` table is the authoritative store;
-- ~/.impact-crater/feedback.jsonl is an append-only event log of POSTs only
-- and does not see these updates.
ALTER TABLE feedback ADD COLUMN triage_note TEXT;
ALTER TABLE feedback ADD COLUMN triaged_at TEXT;
