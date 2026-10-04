import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from obsei import Author, Record, SourceRef, studio
from obsei.ask import ask
from obsei.llm.client import ChatMessage, JsonSchema
from obsei.llm.embed import HashingEmbedder
from obsei.store import Query, Store
from obsei.themes import ThemesConfig, keyword_label, update_themes

NOW = datetime(2026, 9, 20, tzinfo=UTC)
TEXTS = [
    "I cannot log in to the app",
    "I cannot log in to the app!",
    "Login fails, I cannot log in",
    "Cannot log in since update",
    "I cannot log in on my phone",
    "Please refund my double charge",
    "I was charged twice, refund please",
    "Refund the double charge please",
    "Charged twice, need a refund",
    "Refund for double charge requested",
    "No consigo iniciar sesión",
]


def corpus() -> list[Record]:
    return [
        Record(
            source=SourceRef(type="appstore" if i % 2 else "playstore", native_id=str(i)),
            text=text,
            created_at=NOW - timedelta(days=i),
            author=Author(pseudonym=f"psn_{i:032x}"),
            rating=1,
        )
        for i, text in enumerate(TEXTS)
    ]


class FakeChat:
    model = "fake"

    def __init__(self, reply: dict[str, object]) -> None:
        self.reply = reply
        self.messages: list[Sequence[ChatMessage]] = []

    def complete(self, messages: Sequence[ChatMessage], *, schema: JsonSchema) -> str:
        self.messages.append(messages)
        return json.dumps(self.reply)


@pytest.fixture
def store() -> Store:
    s = Store(allow_unencrypted=True)
    s.upsert(corpus())
    return s


def test_themes_are_stable_and_k_anonymous(store: Store) -> None:
    config = ThemesConfig(k_anonymity=5)
    first = update_themes(store, HashingEmbedder(), config)
    assert first.embedded == len(TEXTS)
    assert first.duplicates >= 1
    themes = store.theme_summaries(min_size=5)
    assert sorted(t.size for t in themes) == [5, 5]
    assert all(t.label for t in themes)
    ids = {t.id for t in themes}

    store.upsert(
        [
            Record(
                source=SourceRef(type="appstore", native_id="new"),
                text="I still cannot log in to the app",
                created_at=NOW,
            )
        ]
    )
    second = update_themes(store, HashingEmbedder(), config)
    assert (second.embedded, second.assigned, second.new_themes) == (1, 1, 0)
    assert {t.id for t in store.theme_summaries(min_size=5)} == ids


def test_small_themes_are_hidden_and_not_labelled(store: Store) -> None:
    labeler = FakeChat({"label": "Login problems", "description": "Users cannot sign in."})
    update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=5), labeler)
    labels = {t.label for t in store.theme_summaries(min_size=1)}
    assert "Login problems" in labels
    assert None in labels
    assert len(labeler.messages) == 2


def test_erasure_cascades_to_embeddings_and_themes(store: Store) -> None:
    update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=1))
    store.delete(author_pseudonym=f"psn_{10:032x}")
    assert store.pending_embeddings(HashingEmbedder().model, 100) == []
    assert sum(t.size for t in store.theme_summaries()) == len(TEXTS) - 1
    graph = store.graph(min_size=2)
    kinds = {n.kind for n in graph.nodes}
    assert {"theme", "source"} <= kinds
    assert all(e.weight > 0 for e in graph.edges)


def test_keyword_label_ignores_placeholders() -> None:
    assert keyword_label(["refund <EMAIL> refund", "refund please <EMAIL>"]) == "refund"


def test_ask_cites_only_retrieved_records(store: Store) -> None:
    update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=5))
    login = store.search(Query(text="log in"), limit=1)[0].id
    chat = FakeChat(
        {"answer": f"Login is the top issue [{login}]", "citations": [login, "rec_fake"]}
    )
    answer = ask(store, "Why can't users log in?", chat, embedder=HashingEmbedder())
    assert answer.citations == [login]
    payload = json.loads(chat.messages[0][1]["content"])
    assert payload["themes"]
    assert all("psn_" not in json.dumps(e) for e in payload["evidence"])


def test_erasure_removes_the_record_from_the_theme_centroid() -> None:
    store = Store(allow_unencrypted=True)
    texts = ["Please refund my double charge", "I was charged twice, refund please"]
    store.upsert(
        [
            Record(
                source=SourceRef(type="csv", native_id=str(i)),
                text=text,
                created_at=NOW,
                author=Author(pseudonym=f"psn_{i:032x}"),
            )
            for i, text in enumerate(texts)
        ]
    )
    embedder = HashingEmbedder()
    update_themes(store, embedder, ThemesConfig(k_anonymity=1, similarity=0.2))
    (theme,) = store.theme_summaries()
    assert theme.size == 2
    store.delete(author_pseudonym=f"psn_{0:032x}")
    centroid, size = store.theme_centroid(theme.id)
    (remaining,) = embedder.embed([texts[1]])
    assert size == 1
    assert centroid == pytest.approx(remaining, abs=1e-6)


def test_keyword_label_never_falls_back_to_verbatim_text() -> None:
    samples = ["Paul Smith from Leeds hates checkout", "Terrible payment flow overall"]
    assert keyword_label(samples, fallback="Theme abc123") == "Theme abc123"
    store = Store(allow_unencrypted=True)
    store.upsert(
        [
            Record(
                source=SourceRef(type="csv", native_id=str(i)),
                text=text,
                created_at=NOW,
            )
            for i, text in enumerate(["Margaret Thatcher Road delivery", "Rodrigo Alvarez parcel"])
        ]
    )
    update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=2, similarity=0.01))
    (theme,) = store.theme_summaries(min_size=2)
    assert theme.label == f"Theme {theme.id.removeprefix('thm_')[:6]}"


def test_k_anonymity_counts_people_not_records() -> None:
    store = Store(allow_unencrypted=True)
    one_person = Author(pseudonym="psn_" + "1" * 32)
    store.upsert(
        [
            Record(
                source=SourceRef(type="csv", native_id=f"same-{i}"),
                text="I cannot log in to the app",
                created_at=NOW,
                author=one_person,
                rating=1,
            )
            for i in range(6)
        ]
    )
    config = ThemesConfig(k_anonymity=5)
    update_themes(store, HashingEmbedder(), config)
    assert store.theme_summaries(min_size=1)[0].size == 6
    assert store.theme_summaries(min_size=5) == []
    assert store.unlabeled_themes(5) == []
    assert store.graph(min_size=5).nodes == []
    assert studio.overview(store, k=5).by_source == []
    assert [b.key for b in studio.overview(store, k=1).by_source] == ["csv"]


def test_facets_and_ratings_from_fewer_than_k_people_are_suppressed() -> None:
    store = Store(allow_unencrypted=True)
    store.upsert(
        [
            Record(
                source=SourceRef(type="appstore" if i < 5 else "zendesk", native_id=str(i)),
                text="I cannot log in to the app",
                created_at=NOW,
                author=Author(pseudonym=f"psn_{i:032x}"),
                lang="en" if i < 5 else "is",
                rating=1 if i < 3 else None,
            )
            for i in range(6)
        ]
    )
    update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=5))
    (theme,) = store.theme_summaries(min_size=5)
    assert theme.sources == {"appstore": 5}
    assert theme.languages == {"en": 5}
    assert theme.avg_rating is None
    targets = {e.target for e in store.graph(min_size=5).edges}
    assert targets == {"source:appstore", "lang:en"}
    (everything,) = store.theme_summaries(min_size=1)
    assert everything.sources == {"appstore": 5, "zendesk": 1}
    assert everything.avg_rating == 1
