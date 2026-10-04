"""Runtime services shared by plugins: HTTP, egress policy, pseudonym salt and model endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, Field

from obsei._version import __version__
from obsei.core.record import Author
from obsei.llm.client import OpenAICompatibleClient, RequestBudget
from obsei.llm.egress import EgressPolicy
from obsei.llm.embed import Embedder, HashingEmbedder, RemoteEmbedder
from obsei.privacy.pseudonym import pseudonymize

USER_AGENT = f"obsei/{__version__} (+https://obsei.com)"


class LlmEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    model: str
    api_key_env: str | None = None
    api_key_header: str = Field(
        default="Authorization", description='"api-key" for Azure OpenAI keys.'
    )
    embedding_model: str | None = None
    max_requests: int | None = None
    timeout: float = 60.0


def default_http() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True)


@dataclass
class Context:
    """Without ``salt`` author handles are dropped, never stored in clear."""

    http: httpx.Client = field(default_factory=default_http)
    egress: EgressPolicy = field(default_factory=EgressPolicy)
    salt: bytes | None = None
    llms: Mapping[str, LlmEndpoint] = field(default_factory=dict)
    llm_transport: httpx.BaseTransport | None = None

    def author(self, handle: str | None, locale: str | None = None) -> Author | None:
        if self.salt is None or not handle or not handle.strip():
            return None
        return Author(pseudonym=pseudonymize(handle, self.salt), locale=locale)

    def chat(self, name: str) -> OpenAICompatibleClient:
        try:
            endpoint = self.llms[name]
        except KeyError:
            raise KeyError(f"no llm endpoint named {name!r}") from None
        return OpenAICompatibleClient(
            base_url=endpoint.base_url,
            model=endpoint.model,
            policy=self.egress,
            api_key_env=endpoint.api_key_env,
            api_key_header=endpoint.api_key_header,
            budget=RequestBudget(endpoint.max_requests) if endpoint.max_requests else None,
            timeout=endpoint.timeout,
            transport=self.llm_transport,
        )

    def embedder(self, name: str) -> Embedder:
        """``hashing`` is the built-in offline embedder; other names refer to ``llms``."""
        if name == "hashing":
            return HashingEmbedder()
        model = self.llms[name].embedding_model if name in self.llms else None
        if model is None:
            raise KeyError(f"llm endpoint {name!r} has no embedding_model")
        return RemoteEmbedder(self.chat(name), model)

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
