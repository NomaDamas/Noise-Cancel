from __future__ import annotations

from types import SimpleNamespace

import pytest

from noise_cancel.config import AppConfig
from noise_cancel.dedup.embedder import AbstractEmbedder, SentenceTransformerEmbedder
from noise_cancel.dedup.semantic import (
    SemanticDeduplicator,
    VerificationResult,
    build_verification_system_prompt,
    cosine_similarity,
    deserialize_vector,
    serialize_vector,
)
from noise_cancel.logger.repository import insert_post
from noise_cancel.models import Post


def _post(post_id: str, text: str, platform: str = "linkedin") -> Post:
    return Post(
        id=post_id,
        platform=platform,
        author_name=f"Author-{post_id}",
        post_text=text,
        post_url=f"https://example.com/{post_id}",
    )


def _semantic_config(*, enabled: bool = True, threshold: float = 0.85) -> AppConfig:
    return AppConfig(
        dedup={
            "semantic": {
                "enabled": enabled,
                "provider": "sentence-transformers",
                "model": "all-MiniLM-L6-v2",
                "threshold": threshold,
            }
        }
    )


def test_sentence_transformer_embedder_computes_embeddings(monkeypatch) -> None:
    class FakeEmbeddingArray:
        def __init__(self, rows: list[list[float]]) -> None:
            self._rows = rows

        def tolist(self) -> list[list[float]]:
            return self._rows

    class FakeModel:
        def __init__(self, model_name: str) -> None:
            assert model_name == "test-model"

        def encode(
            self,
            texts: list[str],
            *,
            convert_to_numpy: bool,
            normalize_embeddings: bool,
        ) -> FakeEmbeddingArray:
            assert convert_to_numpy is True
            assert normalize_embeddings is False
            return FakeEmbeddingArray([[float(len(text))] for text in texts])

    def fake_import_module(name: str):
        assert name == "sentence_transformers"
        return SimpleNamespace(SentenceTransformer=FakeModel)

    monkeypatch.setattr("noise_cancel.dedup.embedder.import_module", fake_import_module)

    embedder = SentenceTransformerEmbedder(model="test-model")
    vectors = embedder.embed(["hello", "world!"])

    assert vectors == [[5.0], [6.0]]


def test_vector_blob_round_trip() -> None:
    vector = [0.1, 0.2, 0.3]
    blob = serialize_vector(vector)
    restored = deserialize_vector(blob)

    assert restored == pytest.approx(vector, rel=0, abs=1e-6)


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)


def test_verification_prompt_is_minimal() -> None:
    prompt = build_verification_system_prompt().lower()
    assert "same content: yes/no" in prompt
    assert "one sentence" in prompt


def test_semantic_dedup_marks_duplicate_and_skips_classification(db_connection) -> None:
    existing = _post("p-existing", "Breaking: AI funding round announced", platform="x")
    duplicate = _post("p-duplicate", "AI funding round announced today", platform="reddit")
    insert_post(db_connection, existing)
    insert_post(db_connection, duplicate)

    db_connection.execute(
        "INSERT INTO embeddings (post_id, vector, model, created_at) VALUES (?, ?, ?, ?)",
        ("p-existing", serialize_vector([1.0, 0.0]), "unit-test-embedder", "2026-03-02T00:00:00+00:00"),
    )
    db_connection.commit()

    class FakeEmbedder(AbstractEmbedder):
        model = "unit-test-embedder"

        def embed(self, texts: list[str]) -> list[list[float]]:
            assert texts == [duplicate.post_text]
            return [[0.99, 0.01]]

    verification_calls: list[tuple[str, str]] = []

    def fake_verify(source_text: str, candidate_text: str) -> VerificationResult:
        verification_calls.append((source_text, candidate_text))
        return VerificationResult(is_duplicate=True, reasoning="same announcement across platforms")

    deduplicator = SemanticDeduplicator(
        conn=db_connection,
        config=_semantic_config(enabled=True, threshold=0.85),
        embedder=FakeEmbedder(),
        verifier=fake_verify,
    )

    remaining = deduplicator.deduplicate([duplicate])

    assert remaining == []
    assert verification_calls == [(existing.post_text, duplicate.post_text)]

    duplicate_classification = db_connection.execute(
        "SELECT category, swipe_status, reasoning FROM classifications WHERE post_id = ?",
        ("p-duplicate",),
    ).fetchone()
    assert duplicate_classification is not None
    assert duplicate_classification["category"] == "Duplicate"
    assert duplicate_classification["swipe_status"] == "duplicate"
    assert "same announcement" in duplicate_classification["reasoning"]

    embedding_row = db_connection.execute(
        "SELECT vector, model FROM embeddings WHERE post_id = ?",
        ("p-duplicate",),
    ).fetchone()
    assert embedding_row is not None
    assert embedding_row["model"] == "unit-test-embedder"
    assert deserialize_vector(embedding_row["vector"]) == pytest.approx([0.99, 0.01], rel=0, abs=1e-6)


def test_semantic_dedup_keeps_post_when_verifier_rejects(db_connection) -> None:
    existing = _post("p-existing", "Python 3.13 release notes summary", platform="linkedin")
    candidate = _post("p-candidate", "Python packaging best practices", platform="rss")
    insert_post(db_connection, existing)
    insert_post(db_connection, candidate)

    db_connection.execute(
        "INSERT INTO embeddings (post_id, vector, model, created_at) VALUES (?, ?, ?, ?)",
        ("p-existing", serialize_vector([1.0, 0.0]), "unit-test-embedder", "2026-03-02T00:00:00+00:00"),
    )
    db_connection.commit()

    class FakeEmbedder(AbstractEmbedder):
        model = "unit-test-embedder"

        def embed(self, texts: list[str]) -> list[list[float]]:
            assert texts == [candidate.post_text]
            return [[0.95, 0.05]]

    verify_calls: list[tuple[str, str]] = []

    def fake_verify(source_text: str, candidate_text: str) -> VerificationResult:
        verify_calls.append((source_text, candidate_text))
        return VerificationResult(is_duplicate=False, reasoning="topics overlap but content differs")

    deduplicator = SemanticDeduplicator(
        conn=db_connection,
        config=_semantic_config(enabled=True, threshold=0.85),
        embedder=FakeEmbedder(),
        verifier=fake_verify,
    )

    remaining = deduplicator.deduplicate([candidate])

    assert [post.id for post in remaining] == ["p-candidate"]
    assert verify_calls == [(existing.post_text, candidate.post_text)]

    duplicate_classification = db_connection.execute(
        "SELECT id FROM classifications WHERE post_id = ?",
        ("p-candidate",),
    ).fetchone()
    assert duplicate_classification is None

    embedding_row = db_connection.execute(
        "SELECT vector, model FROM embeddings WHERE post_id = ?",
        ("p-candidate",),
    ).fetchone()
    assert embedding_row is not None
    assert embedding_row["model"] == "unit-test-embedder"
