"""The feedback record: one normalised piece of customer feedback.

Every source maps its native items into ``Record`` objects, so enrichers, sinks,
storage and agents only ever deal with one schema. Identity is pseudonymous by
design: ``Author`` carries a salted pseudonym, never a raw handle.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1"
_ID_RE = re.compile(r"rec_[0-9a-f]{32}")
_HASH_RE = re.compile(r"[0-9a-f]{64}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Normalise text for content hashing: NFKC, case-folded, whitespace collapsed."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class SourceRef(BaseModel):
    """Where a record came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1, description="Source plugin name, e.g. 'appstore'.")
    instance: str = Field(default="default", min_length=1, description="Configured instance.")
    native_id: str = Field(min_length=1, description="The item's id in the source system.")
    url: str | None = None


class Author(BaseModel):
    """A pseudonymous author. Raw identities are never stored here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pseudonym: str = Field(pattern=r"^psn_[0-9a-f]{32}$")
    locale: str | None = None


class Enrichment(BaseModel):
    """The output of one enricher for one record, with provenance."""

    model_config = ConfigDict(extra="forbid")

    value: Any
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = Field(default=None, description="Model or method that produced it.")
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Record(BaseModel):
    """One piece of customer feedback in the obsei Feedback Record schema."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default="", description="Derived from the source identity when omitted.")
    source: SourceRef
    text: str
    created_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    author: Author | None = None
    rating: float | None = None
    lang: str | None = None
    context: dict[str, str] = Field(default_factory=dict)
    enrichments: dict[str, Enrichment] = Field(default_factory=dict)
    content_hash: str = Field(default="", description="SHA-256 of normalised text; derived.")
    purpose: str = Field(default="feedback-analytics", min_length=1)
    schema_version: Literal["0.1"] = "0.1"

    @staticmethod
    def make_id(source: SourceRef) -> str:
        """Stable id derived from the source identity, so re-fetching never duplicates."""
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
        """Return a copy with one enrichment added or replaced."""
        return self.model_copy(update={"enrichments": {**self.enrichments, name: enrichment}})
