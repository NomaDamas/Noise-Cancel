from __future__ import annotations

import json
import math
import re
import sqlite3
import struct
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from typing import TYPE_CHECKING, Any

from noise_cancel.dedup.embedder import AbstractEmbedder, create_embedder_from_config
from noise_cancel.models import Post

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_vector(vector: list[float]) -> bytes:
    if not vector:
        return b""
    return struct.pack(f"<{len(vector)}f", *vector)


def deserialize_vector(blob: bytes) -> list[float]:
    if not blob:
        return []
    if len(blob) % 4 != 0:
        msg = "Embedding BLOB length must be a multiple of 4 bytes"
        raise ValueError(msg)
    dimensions = len(blob) // 4
    return list(struct.unpack(f"<{dimensions}f", blob))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def build_verification_system_prompt() -> str:
    return (
        "You compare two social posts.\nRespond in exactly two lines:\nsame content: yes/no\nreasoning: one sentence."
    )


def _build_verification_user_prompt(source_text: str, candidate_text: str) -> str:
    return f"Post A:\n{source_text}\n\nPost B:\n{candidate_text}"


@dataclass(frozen=True)
class VerificationResult:
    is_duplicate: bool
    reasoning: str


def _parse_verification_response(raw_text: str) -> VerificationResult:
    normalized = raw_text.strip()
    if not normalized:
        return VerificationResult(is_duplicate=False, reasoning="No verifier response received.")

    same_content_match = re.search(r"same\s+content\s*:\s*(yes|no)", normalized, flags=re.IGNORECASE)
    reasoning_match = re.search(r"reasoning\s*:\s*(.+)", normalized, flags=re.IGNORECASE)

    if same_content_match is not None:
        is_duplicate = same_content_match.group(1).strip().lower() == "yes"
    else:
        lowered = normalized.lower()
        is_duplicate = "same content: yes" in lowered or lowered.startswith("yes")

    if reasoning_match is not None:
        reasoning = reasoning_match.group(1).strip()
    else:
        first_line = normalized.splitlines()[0].strip()
        reasoning = first_line or "Verifier did not include reasoning."

    return VerificationResult(is_duplicate=is_duplicate, reasoning=reasoning)


class ClaudeDuplicateVerifier:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        anthropic = import_module("anthropic")
        self._client = anthropic.Anthropic()
        return self._client

    def verify(self, source_text: str, candidate_text: str) -> VerificationResult:
        client = self._get_client()
        model_name = self._config.classifier.get("model", "claude-sonnet-4-6")
        response = client.messages.create(
            model=model_name,
            max_tokens=120,
            temperature=0,
            system=build_verification_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": _build_verification_user_prompt(source_text, candidate_text),
                }
            ],
        )

        text_chunks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return _parse_verification_response("\n".join(text_chunks))


class SemanticDeduplicator:
    def __init__(
        self,
        conn: sqlite3.Connection,
        config: AppConfig,
        *,
        embedder: AbstractEmbedder | None = None,
        verifier: Callable[[str, str], VerificationResult] | None = None,
    ) -> None:
        self._conn = conn
        self._config = config
        semantic_cfg = config.dedup.get("semantic", {})
        self._enabled = bool(semantic_cfg.get("enabled", False))
        self._threshold = float(semantic_cfg.get("threshold", 0.85))
        self._embedder = embedder
        self._verifier = verifier

    def _get_embedder(self) -> AbstractEmbedder:
        if self._embedder is None:
            self._embedder = create_embedder_from_config(self._config)
        return self._embedder

    def _get_verifier(self) -> Callable[[str, str], VerificationResult]:
        if self._verifier is None:
            self._verifier = ClaudeDuplicateVerifier(self._config).verify
        return self._verifier

    def deduplicate(self, posts: list[Post]) -> list[Post]:
        if not posts or not self._enabled:
            return posts

        embedder = self._get_embedder()
        verifier = self._get_verifier()
        vectors = embedder.embed([post.post_text for post in posts])
        if len(vectors) != len(posts):
            msg = "Embedder returned mismatched vector count."
            raise ValueError(msg)

        existing = self._load_embeddings(exclude_post_ids={post.id for post in posts})
        remaining: list[Post] = []
        now_iso = _now_iso()

        for post, vector in zip(posts, vectors, strict=True):
            best_match = self._find_best_match(vector, existing)
            is_duplicate = False

            if best_match is not None:
                verification = verifier(best_match["post_text"], post.post_text)
                if verification.is_duplicate:
                    self._mark_duplicate(post_id=post.id, reason=verification.reasoning, now_iso=now_iso)
                    is_duplicate = True

            self._upsert_embedding(post_id=post.id, vector=vector, model=embedder.model, now_iso=now_iso)
            existing.append({"post_id": post.id, "vector": vector, "post_text": post.post_text})

            if not is_duplicate:
                remaining.append(post)

        self._conn.commit()
        return remaining

    def _load_embeddings(self, *, exclude_post_ids: set[str]) -> list[dict[str, Any]]:
        sql = "SELECT e.post_id, e.vector, p.post_text FROM embeddings e INNER JOIN posts p ON p.id = e.post_id"
        params: list[str] = []
        if exclude_post_ids:
            placeholders = ", ".join("?" for _ in exclude_post_ids)
            sql += f" WHERE e.post_id NOT IN ({placeholders})"
            params = list(exclude_post_ids)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "post_id": row["post_id"],
                "vector": deserialize_vector(row["vector"]),
                "post_text": row["post_text"],
            }
            for row in rows
        ]

    def _find_best_match(self, vector: list[float], existing: list[dict[str, Any]]) -> dict[str, Any] | None:
        best_match: dict[str, Any] | None = None
        best_similarity = self._threshold

        for candidate in existing:
            similarity = cosine_similarity(vector, candidate["vector"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate
        return best_match

    def _upsert_embedding(self, *, post_id: str, vector: list[float], model: str, now_iso: str) -> None:
        self._conn.execute(
            """
            INSERT INTO embeddings (post_id, vector, model, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                vector = excluded.vector,
                model = excluded.model,
                created_at = excluded.created_at
            """,
            (post_id, serialize_vector(vector), model, now_iso),
        )

    def _mark_duplicate(self, *, post_id: str, reason: str, now_iso: str) -> None:
        classification_id = uuid.uuid4().hex
        model_name = str(self._config.classifier.get("model", "semantic-dedup"))
        self._conn.execute(
            """
            INSERT INTO classifications
                (id, post_id, category, confidence, reasoning, summary, applied_rules,
                 model_used, classified_at, delivered, delivered_at, swipe_status, swiped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                category = excluded.category,
                confidence = excluded.confidence,
                reasoning = excluded.reasoning,
                applied_rules = excluded.applied_rules,
                model_used = excluded.model_used,
                classified_at = excluded.classified_at,
                delivered = excluded.delivered,
                delivered_at = excluded.delivered_at,
                swipe_status = excluded.swipe_status,
                swiped_at = excluded.swiped_at
            """,
            (
                classification_id,
                post_id,
                "Duplicate",
                1.0,
                reason,
                "",
                json.dumps(["semantic_dedup"]),
                model_name,
                now_iso,
                0,
                None,
                "duplicate",
                now_iso,
            ),
        )
