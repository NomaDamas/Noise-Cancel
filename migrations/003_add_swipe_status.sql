ALTER TABLE classifications ADD COLUMN swipe_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE classifications ADD COLUMN swiped_at TEXT;

CREATE INDEX idx_classifications_swipe ON classifications(swipe_status);
CREATE INDEX idx_classifications_category ON classifications(category);
