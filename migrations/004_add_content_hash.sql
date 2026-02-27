ALTER TABLE posts ADD COLUMN content_hash TEXT;

CREATE UNIQUE INDEX idx_posts_content_hash ON posts(content_hash);
