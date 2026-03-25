from __future__ import annotations

from noise_cancel.dedup.embedder import (
    AbstractEmbedder,
    OpenAIEmbedder,
    SentenceTransformerEmbedder,
    VoyageEmbedder,
    create_embedder_from_config,
)
from noise_cancel.dedup.semantic import (
    ClaudeDuplicateVerifier,
    SemanticDeduplicator,
    VerificationResult,
    build_verification_system_prompt,
    cosine_similarity,
    deserialize_vector,
    serialize_vector,
)

__all__ = [
    "AbstractEmbedder",
    "ClaudeDuplicateVerifier",
    "OpenAIEmbedder",
    "SemanticDeduplicator",
    "SentenceTransformerEmbedder",
    "VerificationResult",
    "VoyageEmbedder",
    "build_verification_system_prompt",
    "cosine_similarity",
    "create_embedder_from_config",
    "deserialize_vector",
    "serialize_vector",
]
