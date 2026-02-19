from noise_cancel.models import Classification, Post, RunLog


def test_post_creation():
    post = Post(
        id="test-123",
        author_name="John Doe",
        post_text="Hello world",
    )
    assert post.id == "test-123"
    assert post.platform == "linkedin"
    assert post.scraped_at is not None


def test_classification_creation():
    c = Classification(
        id="cls-1",
        post_id="test-123",
        category="Read",
        confidence=0.95,
        reasoning="Contains AI research findings",
        applied_rules=["prioritize_ai_research"],
        model_used="claude-sonnet-4-6",
    )
    assert c.category == "Read"
    assert c.confidence == 0.95
    assert c.delivered is False


def test_run_log_creation():
    log = RunLog(id="run-1", run_type="full")
    assert log.status == "running"
    assert log.posts_scraped == 0


def test_post_to_dict():
    post = Post(id="p1", author_name="Jane", post_text="test")
    d = post.to_dict()
    assert d["id"] == "p1"
    assert d["author_name"] == "Jane"
    assert "scraped_at" in d
