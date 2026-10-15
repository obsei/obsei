"""``obsei try``: which source a link or file maps to, and what redaction and labels did."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pydantic import JsonValue, ValidationError

from obsei.config import SourceEntry
from obsei.core.record import Record
from obsei.enrichers.classify import DecisionClassification
from obsei.studio import PLACEHOLDERS

SOURCES_DOCS = "https://docs.obsei.com/guides/sources/"
TEXT_FIELDS = ("text", "comment", "review", "body", "content", "message", "feedback")
FILE_TYPES = {".csv": "csv", ".jsonl": "jsonl", ".ndjson": "jsonl", ".json": "filedrop"}

Builder = Callable[[re.Match[str]], tuple[str, dict[str, JsonValue]]]


class PreviewError(ValueError):
    pass


def _hn_search(m: re.Match[str]) -> tuple[str, dict[str, JsonValue]]:
    params = parse_qs(urlsplit(m[0]).query)
    query = (params.get("query") or params.get("q") or [""])[0]
    if not query:
        raise PreviewError("a Hacker News search link needs a query (?query=...)")
    return "hackernews", {"query": query, "max_pages": 1}


LINKS: tuple[tuple[re.Pattern[str], Builder], ...] = (
    (
        re.compile(r"https?://apps\.apple\.com/(?P<cc>[a-z]{2})/app/(?:[^/?#]+/)?id(?P<id>\d+)"),
        lambda m: ("appstore", {"app_id": m["id"], "countries": [m["cc"]], "max_pages": 1}),
    ),
    (
        re.compile(r"https?://github\.com/(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?(?:[/?#].*)?$"),
        lambda m: ("github_issues", {"repo": m["repo"], "token_env": None, "max_pages": 1}),
    ),
    (
        re.compile(r"https?://news\.ycombinator\.com/item\?(?:.*&)?id=(?P<id>\d+)"),
        lambda m: ("hackernews", {"story_id": int(m["id"]), "max_pages": 1}),
    ),
    (re.compile(r"https?://hn\.algolia\.com/\?.*"), _hn_search),
    (
        re.compile(r"https?://wordpress\.org/support/plugin/(?P<slug>[\w-]+)/reviews/?$"),
        lambda m: (
            "rss",
            {"url": f"https://wordpress.org/support/plugin/{m['slug']}/reviews/feed/"},
        ),
    ),
    (re.compile(r"https?://\S+"), lambda m: ("rss", {"url": m[0]})),
)
NEEDS_SETUP: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"https?://play\.google\.com/"), "playstore", "a Google Play service account"),
    (
        re.compile(r"https?://(?:www\.|m\.)?youtube\.com/|https?://youtu\.be/"),
        "youtube",
        "an API key",
    ),
    (re.compile(r"https?://bsky\.app/"), "bluesky", "a Bluesky app password"),
)


def _text_field(keys: list[str], where: str) -> str:
    by_name = {k.strip().casefold(): k for k in keys}
    for name in TEXT_FIELDS:
        if name in by_name:
            return by_name[name]
    raise PreviewError(f"{where} has no text column; name it one of: {', '.join(TEXT_FIELDS)}")


def _keys(path: Path, kind: str) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        if kind == "csv":
            return list(csv.DictReader(handle).fieldnames or [])
        if kind == "jsonl":
            first = next((line for line in handle if line.strip()), "{}")
            item: JsonValue = json.loads(first)
        else:
            item = json.load(handle)
            item = item[0] if isinstance(item, list) and item else item
    return list(item) if isinstance(item, dict) else []


def _file(path: Path) -> SourceEntry:
    kind = FILE_TYPES.get(path.suffix.lower())
    if kind is None:
        raise PreviewError(f"{path}: preview reads .csv, .jsonl and .json files")
    try:
        keys = _keys(path, kind)
    except (OSError, ValueError) as exc:
        raise PreviewError(f"cannot read {path}: {exc}") from None
    fields: dict[str, JsonValue] = {"text": _text_field(keys, str(path))}
    for name in ("lang", "rating"):
        if name in keys:
            fields[name] = name
    config: dict[str, JsonValue] = {"fields": fields}
    if kind == "filedrop":
        config |= {"directory": str(path.parent), "pattern": path.name}
    else:
        config["path"] = str(path)
    return SourceEntry(key=kind, type=kind, config=config)


def resolve(target: str) -> SourceEntry:
    """The source for an App Store, GitHub, Hacker News or feed link, or a local file."""
    for pattern, source, needs in NEEDS_SETUP:
        if pattern.match(target):
            raise PreviewError(
                f"previewing {source} needs {needs}: configure the {source} source in obsei.yaml "
                f"({SOURCES_DOCS})"
            )
    if not re.match(r"https?://", target):
        path = Path(target)
        if not path.is_file():
            raise PreviewError(f"{target} is not a link or a file")
        return _file(path)
    for pattern, build in LINKS:
        if m := pattern.match(target):
            source, config = build(m)
            return SourceEntry(key=source, type=source, config=config)
    raise PreviewError(f"cannot preview {target}")


@dataclass(frozen=True)
class Redaction:
    source: str
    before: str
    after: str
    counts: Counter[str]


def redactions(source: str, raw: list[Record], redacted: list[Record]) -> list[Redaction]:
    """Placeholders each record gained; the raw text stays in memory for the preview only."""
    found = []
    for before, after in zip(raw, redacted, strict=True):
        counts = Counter(
            {
                label: gained
                for label in PLACEHOLDERS
                if (gained := after.text.count(f"<{label}>") - before.text.count(f"<{label}>")) > 0
            }
        )
        if counts:
            found.append(Redaction(source, before.text, after.text, counts))
    return found


def labels(record: Record) -> str:
    """``intent 0.83 · sentiment 0.91``, with ``review`` when an answer is under its cutoff."""
    enrichment = record.enrichments.get("classify")
    if enrichment is None:
        return ""
    try:
        result = DecisionClassification.model_validate(enrichment.value)
    except ValidationError:
        return ""
    parts = []
    for name, value in (("intent", result.intent), ("sentiment", result.sentiment)):
        confidence = result.confidences.get(name, enrichment.confidence)
        parts.append(value if confidence is None else f"{value} {confidence:.2f}")
    return " · ".join(parts) + (" · review" if result.review else "")
