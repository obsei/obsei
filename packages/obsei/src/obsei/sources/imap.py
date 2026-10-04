"""Feedback mailboxes over IMAP (support@, feedback@): one record per message."""

from __future__ import annotations

import email
import imaplib
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from email.message import Message
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import html_to_text

Connect = Callable[[str, int], imaplib.IMAP4]


class ImapConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = 993
    username_env: str = "IMAP_USERNAME"
    password_env: str = "IMAP_PASSWORD"  # noqa: S105
    folder: str = "INBOX"
    max_messages: int = Field(default=500, ge=1)
    include_subject: bool = True


class ImapError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ImapError(f"{name} is not set")
    return value


def body_text(message: Message) -> str:
    plain: list[str] = []
    html: list[str] = []
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_disposition() == "attachment":
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/plain":
            plain.append(text)
        elif part.get_content_type() == "text/html":
            html.append(html_to_text(text))
    return "\n".join(plain or html).strip()


class ImapSource:
    name: ClassVar[str] = "imap"
    connect: ClassVar[Connect] = imaplib.IMAP4_SSL

    def __init__(self, config: ImapConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        last = cursor.get("uid") if cursor else None
        start = int(last) + 1 if isinstance(last, int) else 1
        client = type(self).connect(c.host, c.port)
        try:
            client.login(_env(c.username_env), _env(c.password_env))
            client.select(c.folder, readonly=True)
            status, data = client.uid("search", f"UID {start}:*")
            if status != "OK":
                raise ImapError(f"IMAP search failed: {status}")
            uids = [int(u) for u in (data[0] or b"").split() if int(u) >= start][: c.max_messages]
            for uid in uids:
                status, parts = client.uid("fetch", str(uid), "(RFC822)")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if status != "OK" or not isinstance(raw, bytes):
                    continue
                record = self._record(email.message_from_bytes(raw, policy=default_policy), uid)
                if record is not None:
                    yield record, {"uid": uid}
        finally:
            client.logout()

    def _record(self, message: Message, uid: int) -> Record | None:
        body = body_text(message)
        subject = str(message.get("Subject", "")).strip()
        parts = [subject] if self.config.include_subject and subject else []
        if body:
            parts.append(body)
        if not parts:
            return None
        try:
            created = parsedate_to_datetime(str(message.get("Date", "")))
        except (TypeError, ValueError):
            created = datetime.now(UTC)
        native_id = str(message.get("Message-ID", "")).strip() or f"uid-{uid}"
        return Record(
            source=SourceRef(
                type=self.name,
                instance=f"{self.config.host}/{self.config.folder}",
                native_id=native_id,
            ),
            text="\n\n".join(parts),
            created_at=created if created.tzinfo else created.replace(tzinfo=UTC),
            author=self.ctx.author(parseaddr(str(message.get("From", "")))[1] or None),
            lang=str(message.get("Content-Language", "")).split(",")[0].strip() or None,
        )
