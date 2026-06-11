-- Purge poisoned score_image cache entries.
--
-- Before the 2026-06-11 cache fix, _payload_path() omitted params_canonical
-- from the payload filename, so every score_image variant for a photo
-- (dimension="quality" + one dimension="narrative_relevance" per brief)
-- shared ONE file on disk; each put() overwrote it and all index rows kept
-- pointing at it. Any score_image cache hit may therefore have returned a
-- value computed for a different dimension or brief. Drop the index rows
-- so the next run re-scores from the provider (Tier-S Flash — cheap).
-- Orphaned payload files on disk are harmless and tiny.

DELETE FROM cache_index WHERE operation = 'score_image';
