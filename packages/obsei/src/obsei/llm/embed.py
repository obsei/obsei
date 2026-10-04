"""Text embeddings: a local hashing embedder (no model, any language) or any
OpenAI-compatible ``/embeddings`` endpoint (Ollama, vLLM, Azure OpenAI, OpenAI, ...)."""

from __future__ import annotations

import hashlib
import math
import unicodedata
from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from obsei.llm.client import LlmError, OpenAICompatibleClient


class Embedder(Protocol):
    @property
    def model(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


class HashingEmbedder:
    """Character n-gram feature hashing. Works offline for every script; weaker than a model."""

    def __init__(self, dimensions: int = 512, ngram: int = 3) -> None:
        self.dimensions = dimensions
        self.ngram = ngram

    @property
    def model(self) -> str:
        return f"hashing-{self.dimensions}-{self.ngram}"

    def _vector(self, text: str) -> list[float]:
        cleaned = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
        padded = f" {cleaned} "
        vector = [0.0] * self.dimensions
        for i in range(max(1, len(padded) - self.ngram + 1)):
            digest = hashlib.blake2b(padded[i : i + self.ngram].encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            vector[value % self.dimensions] += 1.0 if value >> 63 else -1.0
        return normalize(vector)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class _Item(BaseModel):
    embedding: list[float]
    index: int = 0


class _Embeddings(BaseModel):
    data: list[_Item]


class RemoteEmbedder:
    def __init__(self, client: OpenAICompatibleClient, model: str) -> None:
        self.client = client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        content = self.client.post_json("/embeddings", {"model": self._model, "input": list(texts)})
        items = sorted(_Embeddings.model_validate_json(content).data, key=lambda i: i.index)
        if len(items) != len(texts):
            raise LlmError(
                f"embedding endpoint returned {len(items)} vectors for {len(texts)} texts"
            )
        return [normalize(i.embedding) for i in items]
