-- Screenshot path for feedback items (A-023 enhancement).
--
-- When the user submits feedback the frontend captures a PNG of the whole
-- page (html-to-image) and the backend saves it under
-- ~/.impact-crater/feedback_screenshots/{id}.png. This column stores that
-- path so a later Claude session (or the user) can look at exactly what the
-- user was seeing when they flagged the decision.

ALTER TABLE feedback ADD COLUMN screenshot_path TEXT;
