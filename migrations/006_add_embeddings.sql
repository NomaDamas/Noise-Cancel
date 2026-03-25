CREATE TABLE IF NOT EXISTS embeddings (
    post_id    TEXT PRIMARY KEY REFERENCES posts(id),
    vector     BLOB NOT NULL,
    model      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
