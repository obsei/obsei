"""Text embeddings: a local hashing embedder (no model, any language) or any
OpenAI-compatible ``/embeddings`` endpoint (Ollama, vLLM, Azure OpenAI, OpenAI, ...)."""

from __future__ import annotations

import hashlib
import math
import os
import unicodedata
from collections.abc import Iterable, Sequence
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


LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELS_DIR_ENV = "OBSEI_MODELS_DIR"


class _Vector(Protocol):
    def tolist(self) -> list[float]: ...


class _LocalModel(Protocol):
    def embed(self, documents: list[str], batch_size: int) -> Iterable[_Vector]: ...


class LocalEmbedder:
    """A multilingual sentence model run on CPU with ONNX (``pip install 'obsei[embeddings]'``).

    Groups feedback by meaning across languages. When ``offline`` is true the model must already
    be in ``cache_dir`` (``OBSEI_MODELS_DIR``); run ``obsei models download`` once with network.
    """

    def __init__(
        self, model: str = LOCAL_MODEL, *, cache_dir: str | None = None, offline: bool
    ) -> None:
        try:
            from fastembed import TextEmbedding  # noqa: PLC0415
        except ImportError:
            raise LlmError("local embeddings need: pip install 'obsei[embeddings]'") from None
        self._model = model
        try:
            self._engine: _LocalModel = TextEmbedding(
                model_name=model,
                cache_dir=cache_dir or os.environ.get(MODELS_DIR_ENV),
                local_files_only=offline,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            hint = f"; download it first with: obsei models download {model}" if offline else ""
            raise LlmError(f"cannot load embedding model {model!r}: {exc}{hint}") from None

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [normalize(v.tolist()) for v in self._engine.embed(list(texts), batch_size=32)]
