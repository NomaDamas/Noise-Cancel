CREATE TABLE IF NOT EXISTS feedback (
    id                TEXT PRIMARY KEY,
    classification_id TEXT REFERENCES classifications(id),
    action            TEXT NOT NULL CHECK (action IN ('archive', 'delete')),
    platform          TEXT,
    category          TEXT,
    confidence        REAL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_classification_id ON feedback(classification_id);
CREATE INDEX IF NOT EXISTS idx_feedback_platform_action ON feedback(platform, action);
CREATE INDEX IF NOT EXISTS idx_feedback_category_action ON feedback(category, action);
