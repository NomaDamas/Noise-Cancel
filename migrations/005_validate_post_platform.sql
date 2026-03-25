DROP TRIGGER IF EXISTS trg_posts_platform_validate_insert;
CREATE TRIGGER trg_posts_platform_validate_insert
BEFORE INSERT ON posts
FOR EACH ROW
WHEN NEW.platform NOT IN ('linkedin', 'x', 'threads', 'reddit', 'rss')
BEGIN
    SELECT RAISE(ABORT, 'invalid posts.platform value');
END;

DROP TRIGGER IF EXISTS trg_posts_platform_validate_update;
CREATE TRIGGER trg_posts_platform_validate_update
BEFORE UPDATE OF platform ON posts
FOR EACH ROW
WHEN NEW.platform NOT IN ('linkedin', 'x', 'threads', 'reddit', 'rss')
BEGIN
    SELECT RAISE(ABORT, 'invalid posts.platform value');
END;
