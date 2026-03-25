CREATE TABLE IF NOT EXISTS notes (
    id                TEXT PRIMARY KEY,
    classification_id TEXT NOT NULL UNIQUE REFERENCES classifications(id),
    note_text         TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
