"""Helpdesk tickets: Zendesk, Freshdesk and Intercom (your API credentials, incremental)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, html_to_text, lookup, parse_time


class HelpdeskError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise HelpdeskError(f"{name} is not set")
    return value


def _get(ctx: Context, url: str, *, params: dict[str, str | int], auth: httpx.Auth) -> JsonValue:
    response = ctx.http.get(url, params=params, auth=auth)
    if response.is_error:
        raise HelpdeskError(f"{url} returned {response.status_code}")
    payload: JsonValue = response.json()
    return payload


def _tags(value: JsonValue) -> str | None:
    if not isinstance(value, list):
        return None
    names = [as_text(lookup(t, "name")) if isinstance(t, dict) else as_text(t) for t in value]
    return ", ".join(n for n in names if n) or None


def _ticket(
    ctx: Context,
    *,
    kind: str,
    instance: str,
    native_id: str | None,
    subject: str | None,
    body: str | None,
    created: datetime | None,
    requester: str | None,
    url: str | None,
    context: dict[str, str | None],
    rating: float | None = None,
) -> Record | None:
    text = "\n\n".join(p for p in (subject, body) if p)
    if not native_id or not text or created is None:
        return None
    return Record(
        source=SourceRef(type=kind, instance=instance, native_id=native_id, url=url),
        text=text,
        created_at=created,
        author=ctx.author(f"{kind}:{requester}" if requester else None),
        rating=rating,
        context={k: v for k, v in context.items() if v},
    )


class ZendeskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subdomain: str = Field(pattern=r"^[a-z0-9-]+$")
    email_env: str = "ZENDESK_EMAIL"
    token_env: str = "ZENDESK_API_TOKEN"  # noqa: S105
    start_time: datetime = datetime(2020, 1, 1, tzinfo=UTC)
    max_pages: int = Field(default=50, ge=1)


class ZendeskSource:
    name: ClassVar[str] = "zendesk"

    def __init__(self, config: ZendeskConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.base = f"https://{config.subdomain}.zendesk.com"

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        auth = httpx.BasicAuth(f"{_env(c.email_env)}/token", _env(c.token_env))
        after = cursor.get("cursor") if cursor else None
        params: dict[str, str | int] = (
            {"cursor": after}
            if isinstance(after, str)
            else {"start_time": int(c.start_time.timestamp())}
        )
        for _ in range(c.max_pages):
            page = _get(
                self.ctx,
                f"{self.base}/api/v2/incremental/tickets/cursor.json",
                params=params,
                auth=auth,
            )
            token = as_text(lookup(page, "after_cursor"))
            tickets = lookup(page, "tickets")
            state: Cursor = {"cursor": token} if token else dict(cursor or {})
            for ticket in tickets if isinstance(tickets, list) else []:
                ticket_id = as_text(lookup(ticket, "id"))
                record = _ticket(
                    self.ctx,
                    kind=self.name,
                    instance=c.subdomain,
                    native_id=ticket_id,
                    subject=as_text(lookup(ticket, "subject")),
                    body=as_text(lookup(ticket, "description")),
                    created=parse_time(lookup(ticket, "created_at")),
                    requester=as_text(lookup(ticket, "requester_id")),
                    url=f"{self.base}/agent/tickets/{ticket_id}",
                    context={
                        "status": as_text(lookup(ticket, "status")),
                        "channel": as_text(lookup(ticket, "via.channel")),
                        "tags": _tags(lookup(ticket, "tags")),
                        "satisfaction": as_text(lookup(ticket, "satisfaction_rating.score")),
                    },
                )
                if record is not None:
                    yield record, state
            if lookup(page, "end_of_stream") is not False or token is None:
                return
            params = {"cursor": token}


class FreshdeskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(pattern=r"^[a-z0-9-]+$", description="<domain>.freshdesk.com")
    api_key_env: str = "FRESHDESK_API_KEY"
    since: datetime = datetime(2020, 1, 1, tzinfo=UTC)
    max_pages: int = Field(default=300, ge=1, le=300)


class FreshdeskSource:
    name: ClassVar[str] = "freshdesk"

    def __init__(self, config: FreshdeskConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.base = f"https://{config.domain}.freshdesk.com"

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        auth = httpx.BasicAuth(_env(c.api_key_env), "X")
        seen = cursor.get("since") if cursor else None
        since = seen if isinstance(seen, str) else c.since.isoformat()
        newest = since
        for page in range(1, c.max_pages + 1):
            tickets = _get(
                self.ctx,
                f"{self.base}/api/v2/tickets",
                auth=auth,
                params={
                    "updated_since": since,
                    "order_by": "updated_at",
                    "order_type": "asc",
                    "include": "description",
                    "per_page": 100,
                    "page": page,
                },
            )
            if not isinstance(tickets, list) or not tickets:
                return
            for ticket in tickets:
                newest = as_text(lookup(ticket, "updated_at")) or newest
                ticket_id = as_text(lookup(ticket, "id"))
                record = _ticket(
                    self.ctx,
                    kind=self.name,
                    instance=c.domain,
                    native_id=ticket_id,
                    subject=as_text(lookup(ticket, "subject")),
                    body=as_text(lookup(ticket, "description_text")),
                    created=parse_time(lookup(ticket, "created_at")),
                    requester=as_text(lookup(ticket, "requester_id")),
                    url=f"{self.base}/a/tickets/{ticket_id}",
                    context={
                        "tags": _tags(lookup(ticket, "tags")),
                        "status": as_text(lookup(ticket, "status")),
                    },
                )
                if record is not None:
                    yield record, {"since": newest}


IntercomRegion = Literal["us", "eu", "au"]
INTERCOM_HOSTS: dict[IntercomRegion, str] = {
    "us": "https://api.intercom.io",
    "eu": "https://api.eu.intercom.io",
    "au": "https://api.au.intercom.io",
}


class IntercomConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: IntercomRegion = "us"
    token_env: str = "INTERCOM_TOKEN"  # noqa: S105
    workspace: str = "default"
    max_pages: int = Field(default=50, ge=1)


class IntercomSource:
    name: ClassVar[str] = "intercom"

    def __init__(self, config: IntercomConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        headers = {"Authorization": f"Bearer {_env(c.token_env)}", "Intercom-Version": "2.11"}
        seen = cursor.get("updated_at") if cursor else None
        since = seen if isinstance(seen, int) else 0
        body: dict[str, JsonValue] = {
            "query": {"field": "updated_at", "operator": ">", "value": since},
            "sort": {"field": "updated_at", "order": "ascending"},
            "pagination": {"per_page": 150},
        }
        newest = since
        for _ in range(c.max_pages):
            response = self.ctx.http.post(
                f"{INTERCOM_HOSTS[c.region]}/conversations/search", json=body, headers=headers
            )
            if response.is_error:
                raise HelpdeskError(f"Intercom returned {response.status_code}")
            page: JsonValue = response.json()
            conversations = lookup(page, "conversations")
            for conversation in conversations if isinstance(conversations, list) else []:
                updated = as_float(lookup(conversation, "updated_at"))
                newest = max(newest, int(updated or 0))
                created = as_float(lookup(conversation, "created_at"))
                record = _ticket(
                    self.ctx,
                    kind=self.name,
                    instance=c.workspace,
                    native_id=as_text(lookup(conversation, "id")),
                    subject=html_to_text(as_text(lookup(conversation, "source.subject")) or ""),
                    body=html_to_text(as_text(lookup(conversation, "source.body")) or ""),
                    created=None if created is None else datetime.fromtimestamp(created, UTC),
                    requester=as_text(lookup(conversation, "source.author.id")),
                    url=as_text(lookup(conversation, "source.url")),
                    context={
                        "state": as_text(lookup(conversation, "state")),
                        "tags": _tags(lookup(conversation, "tags.tags")),
                    },
                    rating=as_float(lookup(conversation, "conversation_rating.rating")),
                )
                if record is not None:
                    yield record, {"updated_at": newest}
            after = as_text(lookup(page, "pages.next.starting_after"))
            if after is None:
                return
            body["pagination"] = {"per_page": 150, "starting_after": after}
