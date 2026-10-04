"""Chat client for OpenAI-compatible endpoints: Ollama, vLLM, llama.cpp, Azure OpenAI, OpenAI,
Mistral, Groq, OpenRouter, and LiteLLM proxy (for Bedrock, Vertex and others)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Literal, Protocol, TypedDict

import httpx
from pydantic import BaseModel, JsonValue

from obsei.llm.egress import EgressPolicy


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


JsonSchema = dict[str, JsonValue]


class LlmError(RuntimeError):
    pass


class BudgetExceededError(LlmError):
    pass


class ChatClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete(self, messages: Sequence[ChatMessage], *, schema: JsonSchema) -> str: ...


class RequestBudget:
    def __init__(self, max_requests: int) -> None:
        self.max_requests = max_requests
        self.used = 0

    def charge(self) -> None:
        if self.used >= self.max_requests:
            raise BudgetExceededError(f"request budget of {self.max_requests} exhausted")
        self.used += 1


class _Message(BaseModel):
    content: str | None = None


class _Choice(BaseModel):
    message: _Message


class _Completion(BaseModel):
    choices: list[_Choice]


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        policy: EgressPolicy,
        api_key_env: str | None = None,
        budget: RequestBudget | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        policy.check(base_url)
        headers = {}
        if api_key_env:
            key = os.environ.get(api_key_env)
            if not key:
                raise LlmError(f"{api_key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        self._model = model
        self._budget = budget
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    @property
    def model(self) -> str:
        return self._model

    def complete(self, messages: Sequence[ChatMessage], *, schema: JsonSchema) -> str:
        if self._budget is not None:
            self._budget.charge()
        payload: dict[str, JsonValue] = {
            "model": self._model,
            "temperature": 0,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": schema, "strict": True},
            },
        }
        try:
            response = self._http.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlmError(f"model request failed: {exc}") from None
        completion = _Completion.model_validate_json(response.content)
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise LlmError("model returned no content")
        return content

    def close(self) -> None:
        self._http.close()
