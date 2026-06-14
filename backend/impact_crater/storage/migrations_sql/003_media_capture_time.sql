-- Capture-time + GPS columns on media (A-021 / N-014).
--
-- Before this, ingest stored only size + dimensions + perceptual hashes;
-- the capture timestamp sitting in EXIF and the filename (and the GPS in
-- EXIF) were thrown away, so the pipeline had no real chronology and the
-- narrative judge ordered clips with zero time grounding. These columns
-- persist the reconciled capture time (EXIF > filename > mtime), its
-- source + confidence, and the real GPS coordinates for later trip
-- segmentation.

ALTER TABLE media ADD COLUMN capture_timestamp   TEXT;     -- ISO 8601
ALTER TABLE media ADD COLUMN capture_source      TEXT;     -- exif/filename/file_mtime/none
ALTER TABLE media ADD COLUMN capture_confidence  REAL NOT NULL DEFAULT 0;
ALTER TABLE media ADD COLUMN gps_lat             REAL;
ALTER TABLE media ADD COLUMN gps_lon             REAL;

CREATE INDEX IF NOT EXISTS media_capture_time_idx ON media(capture_timestamp);
