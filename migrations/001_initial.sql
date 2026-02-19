CREATE TABLE IF NOT EXISTS run_logs (
    id               TEXT PRIMARY KEY,
    run_type         TEXT NOT NULL,
    started_at       TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at      TEXT,
    status           TEXT NOT NULL DEFAULT 'running',
    posts_scraped    INTEGER DEFAULT 0,
    posts_classified INTEGER DEFAULT 0,
    posts_delivered  INTEGER DEFAULT 0,
    error_message    TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    platform        TEXT NOT NULL DEFAULT 'linkedin',
    author_name     TEXT NOT NULL,
    author_url      TEXT,
    post_url        TEXT UNIQUE,
    post_text       TEXT NOT NULL,
    media_type      TEXT,
    post_timestamp  TEXT,
    scraped_at      TEXT NOT NULL DEFAULT (datetime('now')),
    run_id          TEXT REFERENCES run_logs(id)
);

CREATE TABLE IF NOT EXISTS classifications (
    id              TEXT PRIMARY KEY,
    post_id         TEXT NOT NULL UNIQUE REFERENCES posts(id),
    category        TEXT NOT NULL,
    confidence      REAL NOT NULL,
    reasoning       TEXT NOT NULL,
    applied_rules   TEXT NOT NULL DEFAULT '[]',
    model_used      TEXT NOT NULL,
    classified_at   TEXT NOT NULL DEFAULT (datetime('now')),
    delivered       INTEGER NOT NULL DEFAULT 0,
    delivered_at    TEXT
);
