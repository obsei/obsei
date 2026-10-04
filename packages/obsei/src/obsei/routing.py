"""Conditions on enrichment values, shared by sink ``when`` filters and pipeline routes.

A condition maps a dotted path (``classify.intent``, ``classify.fields.urgency``) to a list of
allowed values or to a mapping with ``is``, ``min_confidence``, ``min_probability``, ``gte`` and
``lte``. Two keys are not paths: ``review`` (true or false) matches records an enricher flagged
for review, and ``max_rating`` keeps records rated at or below it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Self, TypeAlias

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)

from obsei.core.record import Enrichment, Record

ROUTE = "route"
UNROUTED = "unrouted"
RESERVED = frozenset({"review", "max_rating"})
_PATH = re.compile(r"^[\w-]+(\.[\w-]+)*$")
_YES = ("true",)


def text(value: object) -> str | None:
    """A string value as-is and a yes/no value as ``"true"`` or ``"false"``; None otherwise."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else None


def _values(raw: object) -> object:
    items = raw if isinstance(raw, list) else [raw]
    return [text(v) if isinstance(v, bool) else v for v in items]


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


class Condition(BaseModel):
    """Every given test must pass. ``gte``/``lte`` take a level name (compared by level order) or
    a number (compared with the expected score)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    is_: Annotated[list[str] | None, BeforeValidator(_values)] = Field(
        default=None, alias="is", min_length=1
    )
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    min_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    gte: str | float | None = None
    lte: str | float | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError(
                "a condition needs at least one of is, min_confidence, min_probability, gte or lte"
            )
        return self

    def matches(self, record: Record, path: str, levels: Sequence[str] | None = None) -> bool:
        found = _resolve(record, path)
        if found is None:
            return False
        if self.is_ is not None and text(found.value) not in self.is_:
            return False
        if self.min_confidence is not None:
            confidence = found.confidence()
            if confidence is None or confidence < self.min_confidence:
                return False
        if self.min_probability is not None:
            p = found.probability(self.is_ or _YES)
            if p is None or p < self.min_probability:
                return False
        return all(
            bound is None or found.compare(bound, levels, at_least=at_least)
            for bound, at_least in ((self.gte, True), (self.lte, False))
        )


@dataclass(frozen=True)
class _Found:
    enrichment: Enrichment
    root: Mapping[str, JsonValue]
    parent: Mapping[str, JsonValue]
    name: str
    value: JsonValue

    def _keyed(self, key: str) -> JsonValue:
        table = self.root.get(key)
        return table.get(self.name) if isinstance(table, dict) else None

    def confidence(self) -> float | None:
        stored = _number(self._keyed("confidences"))
        return self.enrichment.confidence if stored is None else stored

    def probability(self, targets: Sequence[str]) -> float | None:
        stored = self._keyed("probabilities")
        if isinstance(stored, dict):
            return sum(_number(stored.get(t)) or 0.0 for t in targets)
        p_yes = _number(self.parent.get("probability"))
        if p_yes is not None and isinstance(self.value, bool):
            return sum(p_yes if t == "true" else 1.0 - p_yes for t in targets if t in _BOOLS)
        current, confidence = text(self.value), self.enrichment.confidence
        if current is None or confidence is None:
            return None
        return confidence if current in targets else 1.0 - confidence

    def levels(self, configured: Sequence[str] | None) -> Sequence[str] | None:
        stored = self._keyed("levels")
        if isinstance(stored, list) and all(isinstance(level, str) for level in stored):
            return [str(level) for level in stored]
        return configured

    def compare(
        self, bound: str | float, configured: Sequence[str] | None, *, at_least: bool
    ) -> bool:
        levels = self.levels(configured)
        if isinstance(bound, str):
            current = text(self.value)
            if not levels or current not in levels or bound not in levels:
                return False
            actual, expected = float(levels.index(current)), float(levels.index(bound))
        else:
            score = _number(self._keyed("scores"))
            if score is None:
                score = _number(self.value)
            if score is None and levels and text(self.value) in levels:
                score = float(levels.index(str(self.value)))
            if score is None:
                return False
            actual, expected = score, bound
        return actual >= expected if at_least else actual <= expected


_BOOLS = frozenset({"true", "false"})


def _resolve(record: Record, path: str) -> _Found | None:
    enricher, _, rest = path.partition(".")
    enrichment = record.enrichments.get(enricher)
    if enrichment is None:
        return None
    root = enrichment.value if isinstance(enrichment.value, dict) else {}
    parent: Mapping[str, JsonValue] = {}
    value: JsonValue = enrichment.value
    keys = rest.split(".") if rest else []
    for key in keys:
        if not isinstance(value, dict):
            return None
        parent, value = value, value.get(key)
    return _Found(enrichment, root, parent, keys[-1] if keys else enricher, value)


def flagged(record: Record) -> bool:
    """Whether an enricher marked the record for review (e.g. a decision answer below its
    cutoff that no fallback replaced)."""
    return any(
        isinstance(e.value, dict) and e.value.get("review") is True
        for e in record.enrichments.values()
    )


def _condition(raw: object) -> Condition:
    if isinstance(raw, dict):
        return Condition.model_validate(raw)
    if isinstance(raw, list | str | bool):
        return Condition.model_validate({"is": raw})
    raise ValueError(
        "expected a list of values or a mapping such as {is: ..., min_confidence: ...}"
    )


@dataclass(frozen=True)
class When:
    """Parsed conditions; an empty ``When`` matches every record."""

    conditions: tuple[tuple[str, Condition], ...] = ()
    review: bool | None = None
    max_rating: float | None = None
    levels: Mapping[str, Sequence[str]] = field(default_factory=dict)

    @classmethod
    def parse(
        cls,
        raw: Mapping[str, object] | None,
        *,
        max_rating: float | None = None,
        levels: Mapping[str, Sequence[str]] | None = None,
    ) -> When:
        """Raises ``ValueError`` naming the offending key."""
        conditions: list[tuple[str, Condition]] = []
        review: bool | None = None
        for key, value in (raw or {}).items():
            if key == "review":
                if not isinstance(value, bool):
                    raise ValueError("review: expected true or false")
                review = value
            elif key == "max_rating":
                rating = _number(value)
                if rating is None:
                    raise ValueError("max_rating: expected a number")
                max_rating = rating if max_rating is None else min(max_rating, rating)
            elif not _PATH.fullmatch(key):
                raise ValueError(f"{key!r} is not a dotted path such as classify.intent")
            else:
                try:
                    conditions.append((key, _condition(value)))
                except ValidationError as exc:
                    problems = "; ".join(
                        f"{'.'.join(map(str, e['loc'])) or 'condition'}: {e['msg']}"
                        for e in exc.errors()
                    )
                    raise ValueError(f"{key}: {problems}") from None
                except ValueError as exc:
                    raise ValueError(f"{key}: {exc}") from None
        return cls(tuple(conditions), review, max_rating, dict(levels or {}))

    def matches(self, record: Record) -> bool:
        if self.max_rating is not None and (
            record.rating is None or record.rating > self.max_rating
        ):
            return False
        if self.review is not None and flagged(record) is not self.review:
            return False
        return all(c.matches(record, path, self.levels.get(path)) for path, c in self.conditions)

    def check_levels(self, scores: Mapping[str, Sequence[str] | None]) -> None:
        """Check level bounds against known fields: ``scores`` maps each path a classifier
        answers to its levels (None for fields that are not scores)."""
        for path, condition in self.conditions:
            if path not in scores:
                continue
            known = scores[path]
            for bound in (condition.gte, condition.lte):
                if not isinstance(bound, str):
                    continue
                if known is None:
                    raise ValueError(f"{path}: gte/lte with a level needs a score field")
                if bound not in known:
                    raise ValueError(f"{path}: {bound!r} is not one of the levels {list(known)}")


def _checked(raw: dict[str, JsonValue]) -> dict[str, JsonValue]:
    When.parse(raw)
    return raw


Conditions: TypeAlias = Annotated[dict[str, JsonValue], AfterValidator(_checked)]
"""A ``when`` mapping for plugin configs: validated on load, parsed with ``When.parse``."""


@dataclass(frozen=True)
class Route:
    name: str
    sinks: tuple[str, ...]
    when: When = field(default_factory=When)


@dataclass(frozen=True)
class Router:
    """Ordered routes; the first that matches a record wins."""

    routes: tuple[Route, ...]

    @property
    def targets(self) -> frozenset[str]:
        return frozenset(key for route in self.routes for key in route.sinks)

    def route(self, record: Record) -> Route | None:
        return next((r for r in self.routes if r.when.matches(record)), None)

    def apply(self, record: Record) -> Record:
        """The record with a ``route`` enrichment: ``{"rule": name, "sinks": [...]}``."""
        chosen = self.route(record)
        sinks: list[JsonValue] = list(chosen.sinks) if chosen else []
        value: dict[str, JsonValue] = {"rule": chosen.name if chosen else UNROUTED, "sinks": sinks}
        return record.with_enrichment(ROUTE, Enrichment(value=value))


def routed_to(record: Record) -> frozenset[str]:
    enrichment = record.enrichments.get(ROUTE)
    sinks = (
        enrichment.value.get("sinks") if enrichment and isinstance(enrichment.value, dict) else None
    )
    return (
        frozenset(s for s in sinks if isinstance(s, str))
        if isinstance(sinks, list)
        else frozenset()
    )
