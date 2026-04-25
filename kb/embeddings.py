"""Embedding clients. Voyage primary; OpenAI fallback.

Both providers expose a `.embed(texts) -> list[list[float]]` interface so the
rest of the system never has to care which one is in use.
"""

from __future__ import annotations

from typing import Protocol

from common.settings import settings


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]: ...


class VoyageEmbedder:
    def __init__(self, model: str = "voyage-3", api_key: str | None = None) -> None:
        import voyageai  # local import — optional dep at runtime

        self.client = voyageai.Client(api_key=api_key or settings.voyage_api_key)
        self.model = model
        self.dim = 1024 if model == "voyage-3" else 1024  # voyage-3 family is 1024

    def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        result = self.client.embed(texts, model=self.model, input_type=input_type)
        return result.embeddings


class OpenAIEmbedder:
    def __init__(self, model: str = "text-embedding-3-large", api_key: str | None = None) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key or settings.openai_api_key)
        self.model = model
        self.dim = 3072 if model == "text-embedding-3-large" else 1536

    def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        # OpenAI ignores input_type
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_embedder() -> Embedder:
    provider = settings.embedding_provider.lower()
    if provider == "voyage":
        return VoyageEmbedder(model=settings.embedding_model)
    if provider == "openai":
        return OpenAIEmbedder(model=settings.embedding_model)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider}")
