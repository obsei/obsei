from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

SCHEMA_VERSION = "0.1"
_ID_RE = re.compile(r"rec_[0-9a-f]{32}")
_HASH_RE = re.compile(r"[0-9a-f]{64}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _now() -> datetime:
    return datetime.now(UTC)


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1)
    instance: str = Field(default="default", min_length=1)
    native_id: str = Field(min_length=1)
    url: str | None = None


class Author(BaseModel):
    """Pseudonymous author; raw handles are never stored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pseudonym: str = Field(pattern=r"^psn_[0-9a-f]{32}$")
    locale: str | None = None


class Enrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JsonValue
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = None
    at: datetime = Field(default_factory=_now)


class Record(BaseModel):
    """One piece of customer feedback. ``id`` and ``content_hash`` are derived when omitted."""

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    source: SourceRef
    text: str
    created_at: datetime
    fetched_at: datetime = Field(default_factory=_now)
    author: Author | None = None
    rating: float | None = None
    lang: str | None = None
    context: dict[str, str] = Field(default_factory=dict)
    enrichments: dict[str, Enrichment] = Field(default_factory=dict)
    content_hash: str = ""
    purpose: str = Field(default="feedback-analytics", min_length=1)
    schema_version: Literal["0.1"] = "0.1"

    @staticmethod
    def make_id(source: SourceRef) -> str:
        key = "\x1f".join((source.type, source.instance, source.native_id))
        return f"rec_{_sha256(key)[:32]}"

    @model_validator(mode="after")
    def _derive_and_check(self) -> Self:
        for name in ("created_at", "fetched_at"):
            if getattr(self, name).tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if not self.id:
            self.id = self.make_id(self.source)
        elif not _ID_RE.fullmatch(self.id):
            raise ValueError("id must look like 'rec_' followed by 32 hex characters")
        if not self.content_hash:
            self.content_hash = _sha256(normalize_text(self.text))
        elif not _HASH_RE.fullmatch(self.content_hash):
            raise ValueError("content_hash must be 64 hex characters")
        return self

    def with_enrichment(self, name: str, enrichment: Enrichment) -> Record:
        return self.model_copy(update={"enrichments": {**self.enrichments, name: enrichment}})
