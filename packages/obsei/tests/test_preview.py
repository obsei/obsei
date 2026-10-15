import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import JsonValue

from obsei.core.record import Enrichment, Record, SourceRef
from obsei.preview import PreviewError, labels, redactions, resolve


@pytest.mark.parametrize(
    ("url", "source", "config"),
    [
        (
            "https://apps.apple.com/gb/app/whatsapp-messenger/id310633997",
            "appstore",
            {"app_id": "310633997", "countries": ["gb"], "max_pages": 1},
        ),
        (
            "https://apps.apple.com/us/app/id284882215?see-all=reviews",
            "appstore",
            {"app_id": "284882215", "countries": ["us"], "max_pages": 1},
        ),
        (
            "https://github.com/obsei/obsei/issues?q=is%3Aopen",
            "github_issues",
            {"repo": "obsei/obsei", "token_env": None, "max_pages": 1},
        ),
        (
            "https://github.com/astral-sh/uv.git",
            "github_issues",
            {"repo": "astral-sh/uv", "token_env": None, "max_pages": 1},
        ),
        (
            "https://news.ycombinator.com/item?id=41234567",
            "hackernews",
            {"story_id": 41234567, "max_pages": 1},
        ),
        (
            "https://hn.algolia.com/?dateRange=all&query=duckdb%20encryption&type=story",
            "hackernews",
            {"query": "duckdb encryption", "max_pages": 1},
        ),
        (
            "https://wordpress.org/support/plugin/woocommerce/reviews/",
            "rss",
            {"url": "https://wordpress.org/support/plugin/woocommerce/reviews/feed/"},
        ),
        (
            "https://status.example.com/history.rss",
            "rss",
            {"url": "https://status.example.com/history.rss"},
        ),
    ],
)
def test_links_map_to_sources(url: str, source: str, config: dict[str, JsonValue]) -> None:
    entry = resolve(url)
    assert (entry.type, entry.config) == (source, config)


@pytest.mark.parametrize(
    ("url", "source"),
    [
        ("https://play.google.com/store/apps/details?id=com.whatsapp", "playstore"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
        ("https://bsky.app/search?q=obsei", "bluesky"),
    ],
)
def test_links_that_need_credentials_name_the_source(url: str, source: str) -> None:
    with pytest.raises(PreviewError, match=f"configure the {source} source"):
        resolve(url)


def test_files_map_to_sources_with_their_text_column(tmp_path: Path) -> None:
    csv = tmp_path / "survey.csv"
    csv.write_text("id,Comment,lang\n1,slow,en\n", encoding="utf-8")
    entry = resolve(str(csv))
    assert entry.type == "csv"
    assert entry.config == {"path": str(csv), "fields": {"text": "Comment", "lang": "lang"}}

    jsonl = tmp_path / "tickets.jsonl"
    jsonl.write_text('\n{"body": "crash", "rating": 2}\n', encoding="utf-8")
    assert resolve(str(jsonl)).config["fields"] == {"text": "body", "rating": "rating"}

    array = tmp_path / "export.json"
    array.write_text(json.dumps([{"message": "hi"}]), encoding="utf-8")
    entry = resolve(str(array))
    assert entry.type == "filedrop"
    assert entry.config == {
        "fields": {"text": "message"},
        "directory": str(tmp_path),
        "pattern": "export.json",
    }

    (tmp_path / "no-text.csv").write_text("id,score\n1,9\n", encoding="utf-8")
    with pytest.raises(PreviewError, match="no text column"):
        resolve(str(tmp_path / "no-text.csv"))
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(PreviewError, match=r"\.csv, \.jsonl and \.json"):
        resolve(str(tmp_path / "notes.txt"))


def _record(text: str) -> Record:
    return Record(
        source=SourceRef(type="csv", native_id=text), text=text, created_at=datetime.now(UTC)
    )


def test_redactions_count_only_new_placeholders() -> None:
    raw = [_record("mail a@example.com <EMAIL>"), _record("nothing here")]
    redacted = [_record("mail <EMAIL> <EMAIL>"), _record("nothing here")]
    (found,) = redactions("csv", raw, redacted)
    assert found.counts == {"EMAIL": 1}
    assert found.before == "mail a@example.com <EMAIL>"


def test_labels_show_confidence_and_review() -> None:
    value: dict[str, JsonValue] = {
        "sentiment": "negative",
        "intent": "bug",
        "confidence": 0.41,
        "confidences": {"sentiment": 0.91, "intent": 0.41},
        "review": True,
    }
    record = _record("crash").with_enrichment("classify", Enrichment(value=value, confidence=0.41))
    assert labels(record) == "bug 0.41 · negative 0.91 · review"
    chat = {"sentiment": "positive", "intent": "praise", "language": "en", "confidence": 0.8}
    record = _record("great").with_enrichment("classify", Enrichment(value=chat, confidence=0.8))
    assert labels(record) == "praise 0.80 · positive 0.80"
    assert labels(_record("plain")) == ""
