"""Typeform survey responses through the Responses API, fetched incrementally."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.plugin import factory
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.core.registry import Registry
from obsei.sources._common import as_float, as_text, lookup, parse_time

TEXT_ANSWER = "text"
SINCE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class TypeformError(RuntimeError):
    pass


class TypeformConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form_id: str = Field(pattern=r"^[A-Za-z0-9]+$")
    instance: str | None = Field(default=None, description="Defaults to form_id.")
    token_env: str = "TYPEFORM_TOKEN"  # noqa: S105
    api_base: str = Field(
        default="https://api.typeform.com",
        pattern=r"^https://",
        description="https://api.eu.typeform.com for EU data-center accounts.",
    )
    text_fields: list[str] = Field(
        default_factory=list,
        description="Field refs or ids whose answers form the text; default: all text answers.",
    )
    rating_field: str | None = Field(
        default=None, description="Ref or id of a number, rating, opinion scale or NPS field."
    )
    lang_hidden_field: str | None = None
    author_hidden_field: str | None = Field(
        default=None, description="Hidden field holding a respondent id; pseudonymised."
    )
    since: datetime | None = Field(default=None, description="First run only: oldest response.")
    page_size: int = Field(default=200, ge=1, le=1000)
    max_pages: int = Field(default=50, ge=1)


def _matches(answer: JsonValue, key: str) -> bool:
    return key in (as_text(lookup(answer, "field.ref")), as_text(lookup(answer, "field.id")))


def answer_text(answer: JsonValue) -> str | None:
    kind = as_text(lookup(answer, "type"))
    if kind == "choice":
        return as_text(lookup(answer, "choice.label")) or as_text(lookup(answer, "choice.other"))
    if kind == "choices":
        labels = lookup(answer, "choices.labels")
        parts = [t for t in (as_text(v) for v in labels) if t] if isinstance(labels, list) else []
        other = as_text(lookup(answer, "choices.other"))
        return ", ".join([*parts, *([other] if other else [])]) or None
    if kind == "boolean":
        value = lookup(answer, "boolean")
        return None if not isinstance(value, bool) else ("yes" if value else "no")
    return as_text(lookup(answer, kind)) if kind else None


class TypeformSource:
    """Walks newest to oldest with ``before`` tokens down to the last run's ``since``, so a run
    cut short by ``max_pages`` resumes where it stopped and the cursor only moves forward once
    every response since the previous run has been seen."""

    name: ClassVar[str] = "typeform"

    def __init__(self, config: TypeformConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.instance = config.instance or config.form_id
        self.url = f"{config.api_base.rstrip('/')}/forms/{config.form_id}/responses"

    def _page(self, token: str, since: str | None, before: str | None) -> list[JsonValue]:
        params: dict[str, str | int] = {"page_size": self.config.page_size, "completed": "true"}
        if since:
            start = parse_time(since)
            if start is not None:
                params["since"] = (start - timedelta(seconds=1)).strftime(SINCE_FORMAT)
        if before:
            params["before"] = before
        response = self.ctx.http.get(
            self.url, params=params, headers={"Authorization": f"Bearer {token}"}
        )
        if response.is_error:
            raise TypeformError(f"Typeform returned {response.status_code}")
        payload: JsonValue = response.json()
        items = lookup(payload, "items")
        return items if isinstance(items, list) else []

    def record(self, item: JsonValue) -> Record | None:
        c = self.config
        native_id = as_text(lookup(item, "response_id")) or as_text(lookup(item, "token"))
        created = parse_time(lookup(item, "submitted_at"))
        answers = lookup(item, "answers")
        answers = answers if isinstance(answers, list) else []
        if c.text_fields:
            chosen = [a for key in c.text_fields for a in answers if _matches(a, key)]
        else:
            chosen = [a for a in answers if as_text(lookup(a, "type")) == TEXT_ANSWER]
        text = "\n\n".join(t for t in (answer_text(a) for a in chosen) if t)
        if not native_id or created is None or not text:
            return None
        rating = None
        if c.rating_field:
            scored = [a for a in answers if _matches(a, c.rating_field)]
            rating = as_float(lookup(scored[0], "number")) if scored else None
        lang = (
            as_text(lookup(item, f"hidden.{c.lang_hidden_field}")) if c.lang_hidden_field else None
        )
        handle = (
            as_text(lookup(item, f"hidden.{c.author_hidden_field}"))
            if c.author_hidden_field
            else None
        )
        context = {"form": c.form_id, "platform": as_text(lookup(item, "metadata.platform"))}
        return Record(
            source=SourceRef(type=self.name, instance=self.instance, native_id=native_id),
            text=text,
            created_at=created,
            author=self.ctx.author(handle, lang),
            rating=rating,
            lang=lang,
            context={k: v for k, v in context.items() if v},
        )

    def _walk(
        self, token: str, since: str | None, before: str | None, newest: str | None
    ) -> Iterator[tuple[Record, Cursor]]:
        pending: tuple[Record, Cursor] | None = None
        done = False
        for _ in range(self.config.max_pages):
            items = self._page(token, since, before)
            for item in items:
                submitted = parse_time(lookup(item, "submitted_at"))
                if newest is None and submitted is not None:
                    newest = submitted.isoformat()
                key = as_text(lookup(item, "token")) or as_text(lookup(item, "response_id"))
                before = key or before
                record = self.record(item)
                if record is None or key is None:
                    continue
                if pending is not None:
                    yield pending
                pending = (record, {"since": since, "before": before, "newest": newest})
            if len(items) < self.config.page_size:
                done = True
                break
        if pending is not None:
            yield (pending[0], {"since": newest or since}) if done else pending

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        token = os.environ.get(c.token_env)
        if not token:
            raise TypeformError(f"{c.token_env} is not set")
        saved = cursor or {}
        since = saved.get("since")
        since = since if isinstance(since, str) else (c.since.isoformat() if c.since else None)
        before = saved.get("before")
        if isinstance(before, str):
            newest = saved.get("newest")
            newest = newest if isinstance(newest, str) else None
            resumed = False
            for item in self._walk(token, since, before, newest):
                resumed = True
                yield item
            if resumed:
                return
            since = newest or since
        yield from self._walk(token, since, None, None)


def register(registry: Registry) -> None:
    registry.add_source("typeform", factory(TypeformConfig, TypeformSource))
