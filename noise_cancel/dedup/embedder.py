from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from importlib import import_module
from typing import TYPE_CHECKING, Any

import httpx

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig


class AbstractEmbedder(ABC):
    model: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class SentenceTransformerEmbedder(AbstractEmbedder):
    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self.model = model
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        sentence_transformers = import_module("sentence_transformers")
        model_class = getattr(sentence_transformers, "SentenceTransformer", None)
        if model_class is None:
            msg = "sentence_transformers.SentenceTransformer is unavailable"
            raise ImportError(msg)

        self._model = model_class(self.model)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        encoded = model.encode(texts, convert_to_numpy=True, normalize_embeddings=False)
        rows = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
        return [[float(value) for value in row] for row in rows]


class OpenAIEmbedder(AbstractEmbedder):
    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self._api_key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

        if not self._api_key:
            msg = "OPENAI_API_KEY is required for OpenAIEmbedder"
            raise ValueError(msg)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = httpx.post(
                f"{self._base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()

            payload = response.json()
            data = payload.get("data", [])
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            return [[float(value) for value in item.get("embedding", [])] for item in ordered]
        except httpx.HTTPError as exc:
            logger.warning("OpenAI embedding request failed: %s", exc)
            return []
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("OpenAI embedding response parsing failed: %s", exc)
            return []


class VoyageEmbedder(AbstractEmbedder):
    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.voyageai.com/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self._api_key = (api_key or os.environ.get("VOYAGE_API_KEY", "")).strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

        if not self._api_key:
            msg = "VOYAGE_API_KEY is required for VoyageEmbedder"
            raise ValueError(msg)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = httpx.post(
                f"{self._base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()

            payload = response.json()
            data = payload.get("data", [])
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            return [[float(value) for value in item.get("embedding", [])] for item in ordered]
        except httpx.HTTPError as exc:
            logger.warning("Voyage embedding request failed: %s", exc)
            return []
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Voyage embedding response parsing failed: %s", exc)
            return []


def create_embedder_from_config(config: AppConfig) -> AbstractEmbedder:
    semantic_cfg = config.dedup.get("semantic", {})
    provider = str(semantic_cfg.get("provider", "sentence-transformers")).strip().lower()
    model = str(semantic_cfg.get("model", "all-MiniLM-L6-v2")).strip()

    if provider in {"sentence-transformers", "sentence_transformers"}:
        return SentenceTransformerEmbedder(model=model)
    if provider == "openai":
        return OpenAIEmbedder(model=model)
    if provider == "voyage":
        return VoyageEmbedder(model=model)

    msg = f"Unsupported semantic dedup provider: {provider}"
    raise ValueError(msg)
