"""Client for decision models (Julia-1, Kev-4B, Clef, OpenJev and others) served by llama.cpp, the
OpenJev helper, hosted Jev or Cloudflare Workers AI. The model scores the options it is given in
one pass, so an answer is always one of them, with probabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, TypeAlias

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from obsei.llm.client import LlmError, LlmUnreachableError, RequestBudget, auth_headers
from obsei.llm.egress import EGRESS, EgressPolicy

URL_HINT = (
    "set url (or url_env) to the full decision endpoint URL your server documents, "
    "e.g. http://127.0.0.1:8080/v1/..."
)
MIN_LEVELS, MAX_LEVELS = 2, 10
_BAD_REQUEST, _NOT_IMPLEMENTED = 400, 501
_DETAIL = 300


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instructions: str = Field(min_length=1)


class ChoiceQuestion(_Question):
    """``criteria`` maps each option to a description (or None). How many options one request
    may carry depends on the model; the server rejects too many."""

    type: Literal["choice"] = "choice"
    criteria: dict[str, str | None] = Field(min_length=2)


class ScoreQuestion(_Question):
    """``criteria`` are the levels, lowest first."""

    type: Literal["score"] = "score"
    criteria: list[str] = Field(min_length=MIN_LEVELS, max_length=MAX_LEVELS)


class YesNoQuestion(_Question):
    """``criteria`` optionally describes what ``true`` and ``false`` mean."""

    type: Literal["noul"] = "noul"
    criteria: dict[Literal["true", "false"], str] | None = None


Question: TypeAlias = Annotated[
    ChoiceQuestion | ScoreQuestion | YesNoQuestion, Field(discriminator="type")
]

Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class ChoiceAnswer(BaseModel):
    """``confidence`` is 0 when all options are equally likely."""

    type: Literal["choice"]
    choice: str
    probabilities: dict[str, Probability] = Field(min_length=1)
    confidence: Probability


class ScoreAnswer(BaseModel):
    """``score`` is the expected level (0 = lowest, may be fractional) and ``label`` the level
    nearest to it; the client re-keys ``probabilities`` from level index to level label."""

    type: Literal["score"]
    score: float
    legend: dict[str, str] = Field(default_factory=dict)
    probabilities: dict[str, Probability] = Field(min_length=1)
    confidence: Probability
    label: str = ""


class YesNoAnswer(BaseModel):
    """``noul`` is the probability of yes (true)."""

    type: Literal["noul"]
    noul: Probability

    @property
    def value(self) -> bool:
        return self.noul >= 0.5  # noqa: PLR2004

    @property
    def confidence(self) -> float:
        return max(self.noul, 1.0 - self.noul)


Answer: TypeAlias = Annotated[ChoiceAnswer | ScoreAnswer | YesNoAnswer, Field(discriminator="type")]


def yes_no(instructions: str, yes: str | None = None, no: str | None = None) -> Question:
    """A yes/no question. With both descriptions it is asked as a choice between ``yes`` and
    ``no``, which small models answer more reliably than a bare yes/no question."""
    if yes and no:
        return ChoiceQuestion(instructions=instructions, criteria={"yes": yes, "no": no})
    return YesNoQuestion(instructions=instructions)


def probability_of_yes(answer: Answer) -> float:
    if isinstance(answer, YesNoAnswer):
        return answer.noul
    if isinstance(answer, ChoiceAnswer):
        return answer.probabilities.get("yes", 1.0 if answer.choice == "yes" else 0.0)
    raise LlmError("a score is not a yes/no answer")


class _Response(BaseModel):
    model: str | None = None
    answers: dict[str, Answer]


class _Envelope(BaseModel):
    """Cloudflare Workers AI wraps the response: ``{"result": {...}, "success": true}``."""

    result: _Response | None = None
    success: bool = True
    errors: list[JsonValue] = Field(default_factory=list)


_QUESTIONS: TypeAdapter[ChoiceQuestion | ScoreQuestion | YesNoQuestion] = TypeAdapter(Question)


def check_url(url: str) -> str:
    """``url`` is the full endpoint URL requests are posted to, unchanged."""
    parsed = httpx.URL(url)
    if parsed.scheme not in ("http", "https") or not parsed.host or parsed.path in ("", "/"):
        raise ValueError(f"{url!r} is not a decision endpoint URL; {URL_HINT}")
    return url


def _question(question: Question) -> JsonValue:
    dumped: dict[str, JsonValue] = _QUESTIONS.dump_python(question, mode="json")
    if isinstance(question, YesNoQuestion) and question.criteria is None:
        del dumped["criteria"]
    return dumped


class DecisionClient:
    def __init__(
        self,
        *,
        url: str,
        policy: EgressPolicy,
        model: str | None = None,
        api_key_env: str | None = None,
        api_key_header: str = "Authorization",
        budget: RequestBudget | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        try:
            self.url = check_url(url)
        except ValueError as exc:
            raise LlmError(str(exc)) from None
        policy.check(self.url)
        self._policy = policy
        self._model = model
        self._served: str | None = None
        self._budget = budget
        self._http = httpx.Client(
            headers=auth_headers(api_key_env, api_key_header),
            timeout=timeout,
            transport=transport,
            event_hooks={"request": [self._guard]},
        )

    def _guard(self, request: httpx.Request) -> None:
        if request.extensions.get("obsei_egress"):
            self._policy.check(str(request.url))

    @property
    def model(self) -> str:
        """The model the server reports, else the configured one, else the endpoint URL."""
        return self._served or self._model or self.url

    def _post(self, payload: dict[str, JsonValue]) -> bytes:
        if self._budget is not None:
            self._budget.charge()
        try:
            response = self._http.post(self.url, json=payload, extensions=EGRESS)
        except httpx.TransportError as exc:
            raise LlmUnreachableError(
                f"cannot reach the decision model at {self.url}: {exc}"
            ) from None
        if response.status_code == _NOT_IMPLEMENTED:
            raise LlmError(
                f"{self.url} is not serving a decision model (or does not support this request)"
            )
        if response.status_code == _BAD_REQUEST:
            raise LlmError(
                f"decision model at {self.url} rejected the request: {response.text[:_DETAIL]}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlmError(f"decision request to {self.url} failed: {exc}") from None
        return response.content

    def _parse(self, content: bytes) -> _Response:
        try:
            envelope = _Envelope.model_validate_json(content)
            if not envelope.success:
                raise LlmError(f"decision model at {self.url} failed: {envelope.errors}")
            return envelope.result or _Response.model_validate_json(content)
        except ValidationError as exc:
            raise LlmError(f"decision model at {self.url} returned invalid JSON: {exc}") from None

    def decide(self, state: JsonValue, questions: Mapping[str, Question]) -> dict[str, Answer]:
        """``state`` is text, or an object or list the server gives the model as JSON."""
        payload: dict[str, JsonValue] = {
            "state": state,
            "questions": {name: _question(q) for name, q in questions.items()},
        }
        if self._model:
            payload["model"] = self._model
        parsed = self._parse(self._post(payload))
        self._served = parsed.model or self._served
        return {
            name: self._check(name, question, parsed.answers.get(name))
            for name, question in questions.items()
        }

    def _check(self, name: str, question: Question, answer: Answer | None) -> Answer:
        def bad(reason: str) -> LlmError:
            return LlmError(f"decision model at {self.url}: {name!r} {reason}")

        if answer is None:
            raise bad("was not answered")
        if answer.type != question.type:
            raise bad(f"was answered as {answer.type}, asked as {question.type}")
        if isinstance(question, ChoiceQuestion) and isinstance(answer, ChoiceAnswer):
            if answer.choice not in question.criteria:
                raise bad(f"chose {answer.choice!r}, which is not one of the options")
            if not set(answer.probabilities) <= set(question.criteria):
                raise bad("has probabilities for unknown options")
        if isinstance(question, ScoreQuestion) and isinstance(answer, ScoreAnswer):
            top = len(question.criteria) - 1
            if not 0 <= answer.score <= top:
                raise bad(f"scored {answer.score}, outside 0-{top}")
            levels = {str(i): level for i, level in enumerate(question.criteria)}
            if not set(answer.probabilities) <= set(levels):
                raise bad("has probabilities for unknown levels")
            return answer.model_copy(
                update={
                    "label": levels[str(round(answer.score))],
                    "probabilities": {levels[k]: p for k, p in answer.probabilities.items()},
                }
            )
        return answer

    def close(self) -> None:
        self._http.close()
