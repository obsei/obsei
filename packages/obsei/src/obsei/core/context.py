"""Runtime services shared by plugins: HTTP, egress policy, pseudonym salt and model endpoints."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Literal, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from obsei._version import __version__
from obsei.core.record import Author
from obsei.llm.client import LlmError, OpenAICompatibleClient, RequestBudget
from obsei.llm.decision import URL_HINT, DecisionClient, check_url
from obsei.llm.egress import EGRESS, EgressPolicy
from obsei.llm.embed import LOCAL_MODEL, Embedder, HashingEmbedder, LocalEmbedder, RemoteEmbedder
from obsei.privacy.pseudonym import pseudonymize

__all__ = ["EGRESS", "USER_AGENT", "Context", "LlmEndpoint", "default_http", "origin"]

USER_AGENT = f"obsei/{__version__} (+https://obsei.com)"


class LlmEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api: Literal["openai", "decision"] = Field(
        default="openai", description='"decision" for decision models (set url, not base_url).'
    )
    base_url: str | None = Field(default=None, description="Chat endpoints: the /v1 base URL.")
    url: str | None = Field(
        default=None, description="Decision endpoints: the full URL requests are posted to."
    )
    url_env: str | None = Field(
        default=None, description="Decision endpoints: environment variable holding the URL."
    )
    model: str | None = Field(default=None, description="Required for openai endpoints.")
    api_key_env: str | None = None
    api_key_header: str = Field(
        default="Authorization", description='"api-key" for Azure OpenAI keys.'
    )
    embedding_model: str | None = None
    max_requests: int | None = None
    timeout: float = 60.0

    @property
    def address(self) -> str:
        return self.url or self.base_url or (f"${self.url_env}" if self.url_env else "")

    def decision_url(self) -> str:
        if self.url:
            return self.url
        value = os.environ.get(self.url_env or "", "").strip()
        if not value:
            raise LlmError(f"{self.url_env} is not set; {URL_HINT}")
        try:
            return check_url(value)
        except ValueError as exc:
            raise LlmError(f"{self.url_env}: {exc}") from None

    @model_validator(mode="after")
    def _shape(self) -> LlmEndpoint:
        if self.api == "decision":
            if self.base_url is not None or (self.url is None) == (self.url_env is None):
                raise ValueError(f"a decision endpoint takes one of url or url_env; {URL_HINT}")
            if self.url is not None:
                check_url(self.url)
            return self
        if self.url is not None or self.url_env is not None or not self.base_url:
            raise ValueError("an openai endpoint takes base_url, not url or url_env")
        if not self.model:
            raise ValueError("an openai endpoint needs a model")
        return self


_ORIGIN_KEY = "obsei_origin"
_FORWARDED_HEADERS = frozenset(
    {"accept", "accept-encoding", "accept-language", "content-type", "content-length", "host"}
    | {"transfer-encoding", "user-agent"}
)
_DEFAULT_PORTS = {"http": 80, "https": 443}


def origin(url: str | httpx.URL) -> tuple[str, str, int | None]:
    """(scheme, host, port) with the default port filled in."""
    parsed = httpx.URL(url)
    return parsed.scheme, parsed.host, parsed.port or _DEFAULT_PORTS.get(parsed.scheme)


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

    def __post_init__(self) -> None:
        hooks = self.http.event_hooks
        self.http.event_hooks = {**hooks, "request": [*hooks["request"], self._guard_request]}

    def _guard_request(self, request: httpx.Request) -> None:
        """Runs for every request and redirect hop: a hop to another origin loses credentials
        and custom headers, and egress-marked requests are checked against the policy."""
        first = request.extensions.setdefault(_ORIGIN_KEY, origin(request.url))
        if first != origin(request.url):
            for name in [n for n in request.headers if n.lower() not in _FORWARDED_HEADERS]:
                del request.headers[name]
        if request.extensions.get("obsei_egress"):
            self.egress.check(str(request.url))

    def author(self, handle: str | None, locale: str | None = None) -> Author | None:
        if self.salt is None or not handle or not handle.strip():
            return None
        return Author(pseudonym=pseudonymize(handle, self.salt), locale=locale)

    def _endpoint(self, name: str) -> LlmEndpoint:
        try:
            return self.llms[name]
        except KeyError:
            raise KeyError(f"no llm endpoint named {name!r}") from None

    def chat(self, name: str) -> OpenAICompatibleClient:
        endpoint = self._endpoint(name)
        if endpoint.api != "openai" or endpoint.base_url is None or endpoint.model is None:
            raise KeyError(f"llm endpoint {name!r} is a decision model, not a chat model")
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

    def decision(self, name: str) -> DecisionClient:
        endpoint = self._endpoint(name)
        if endpoint.api != "decision":
            raise KeyError(f"llm endpoint {name!r} is a chat model; decisions need api: decision")
        return DecisionClient(
            url=endpoint.decision_url(),
            model=endpoint.model,
            policy=self.egress,
            api_key_env=endpoint.api_key_env,
            api_key_header=endpoint.api_key_header,
            budget=RequestBudget(endpoint.max_requests) if endpoint.max_requests else None,
            timeout=endpoint.timeout,
            transport=self.llm_transport,
        )

    def embedder(self, name: str) -> Embedder:
        """``hashing`` (built in), ``local`` or ``local:<model>`` (``obsei[embeddings]``, groups
        by meaning across languages), or an ``llms`` name with ``embedding_model``."""
        if name == "hashing":
            return HashingEmbedder()
        if name == "local" or name.startswith("local:"):
            local = name.partition(":")[2] or LOCAL_MODEL
            return LocalEmbedder(local, offline=self.egress.mode == "air_gapped")
        remote = self.llms[name].embedding_model if name in self.llms else None
        if remote is None:
            raise KeyError(f"llm endpoint {name!r} has no embedding_model")
        return RemoteEmbedder(self.chat(name), remote)

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
