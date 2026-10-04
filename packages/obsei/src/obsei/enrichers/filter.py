"""One yes/no question to a decision model per record: spam, bots, off-topic. Matching records are
tagged, or dropped before later enrichers, sinks and the store."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from obsei.core.context import Context
from obsei.core.record import Enrichment, Record
from obsei.enrichers.classify import decision_state
from obsei.llm.client import LlmError
from obsei.llm.decision import DecisionClient, probability_of_yes, yes_no


class FilterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: str = Field(default="default", description="An llms endpoint with api: decision.")
    question: str = Field(
        min_length=1, description='A yes/no question; "yes" matches, e.g. "Is this spam?".'
    )
    yes_means: str | None = Field(
        default=None,
        description="With no_means: describe both answers to ask a two-option choice, which "
        "small models answer more reliably.",
    )
    no_means: str | None = None
    threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Probability of yes from which a record matches."
    )
    action: Literal["drop", "tag"] = "tag"

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        if bool(self.yes_means) != bool(self.no_means):
            raise ValueError("yes_means and no_means go together")
        return self


class DecisionFilter:
    """Enrichment value: ``{"match": bool, "probability": p_yes, "action": ...}``."""

    name: ClassVar[str] = "filter"
    version: ClassVar[str] = "1"

    def __init__(
        self,
        client: DecisionClient,
        question: str,
        *,
        yes: str | None = None,
        no: str | None = None,
        threshold: float = 0.5,
        action: Literal["drop", "tag"] = "tag",
    ) -> None:
        self.client = client
        self.question = yes_no(question, yes, no)
        self.threshold = threshold
        self.action = action
        self.last_error: str | None = None

    def _probability(self, record: Record) -> float | None:
        try:
            answer = self.client.decide(decision_state(record), {"match": self.question})["match"]
        except LlmError as exc:
            self.last_error = str(exc)
            return None
        return probability_of_yes(answer)

    def enrich(self, batch: Sequence[Record]) -> list[Enrichment | None]:
        results: list[Enrichment | None] = []
        for record in batch:
            p = self._probability(record)
            results.append(
                None
                if p is None
                else Enrichment(
                    value={"match": p >= self.threshold, "probability": p, "action": self.action},
                    confidence=max(p, 1.0 - p),
                    model=self.client.model,
                )
            )
        return results

    def keep(self, record: Record) -> bool:
        enrichment = record.enrichments.get(self.name)
        if self.action != "drop" or enrichment is None or not isinstance(enrichment.value, dict):
            return True
        return enrichment.value.get("match") is not True


def build_filter(config: FilterConfig, ctx: Context) -> DecisionFilter:
    return DecisionFilter(
        ctx.decision(config.llm),
        config.question,
        yes=config.yes_means,
        no=config.no_means,
        threshold=config.threshold,
        action=config.action,
    )
