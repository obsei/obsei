"""Read-only Studio data: k-anonymous aggregates, themes, the knowledge graph and evidence.

The same snapshot backs the live API (``obsei serve``) and the static export (``obsei studio``).
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, Field

from obsei._version import __version__
from obsei.access import Role
from obsei.evidence import Evidence, ThemeInfo, evidence
from obsei.store import GroupBy, Query, Store

STATIC_FILES = ("app.js", "styles.css", "logo.png")
LIVE_DATA = '<meta name="obsei-data" content="api" />'
EXPORT_DATA = '<meta name="obsei-data" content="data.json" />'
TIME_GROUPS: tuple[GroupBy, ...] = ("day", "week", "month")


class Bucket(BaseModel):
    key: str
    count: int
    avg_rating: float | None


class Overview(BaseModel):
    generated_at: datetime
    version: str
    k_anonymity: int
    total: int
    by_source: list[Bucket]
    by_sentiment: list[Bucket]
    by_intent: list[Bucket]
    by_lang: list[Bucket]
    by_week: list[Bucket]


class Node(BaseModel):
    id: str
    kind: str
    label: str
    weight: int


class Edge(BaseModel):
    source: str
    target: str
    weight: int


class GraphView(BaseModel):
    nodes: list[Node]
    edges: list[Edge]


class Snapshot(BaseModel):
    demo: bool = False
    embedder: str | None = None
    role: Role | None = None
    overview: Overview
    themes: list[ThemeInfo]
    graph: GraphView
    evidence: dict[str, list[Evidence]] = Field(default_factory=dict)


def _buckets(store: Store, group_by: GroupBy, k: int) -> list[Bucket]:
    return [
        Bucket(key=r.key, count=r.count, avg_rating=r.avg_rating)
        for r in store.stats(Query(), group_by, limit=200)
        if r.key is not None and (r.people >= k or group_by in TIME_GROUPS)
    ]


def overview(store: Store, *, k: int) -> Overview:
    return Overview(
        generated_at=datetime.now(UTC),
        version=__version__,
        k_anonymity=k,
        total=store.count(),
        by_source=_buckets(store, "source", k),
        by_sentiment=_buckets(store, "sentiment", k),
        by_intent=_buckets(store, "intent", k),
        by_lang=_buckets(store, "lang", k),
        by_week=_buckets(store, "week", k)[-26:],
    )


def themes(store: Store, *, k: int) -> list[ThemeInfo]:
    return [
        ThemeInfo.model_validate(t, from_attributes=True) for t in store.theme_summaries(min_size=k)
    ]


def graph(store: Store, *, k: int) -> GraphView:
    g = store.graph(min_size=k)
    kept = {n.id for n in g.nodes if n.weight >= k}
    return GraphView(
        nodes=[Node.model_validate(n, from_attributes=True) for n in g.nodes if n.id in kept],
        edges=[
            Edge.model_validate(e, from_attributes=True)
            for e in g.edges
            if e.source in kept and e.target in kept
        ],
    )


def theme_evidence(store: Store, theme_id: str, *, k: int, limit: int = 20) -> list[Evidence]:
    if not any(t.id == theme_id for t in store.theme_summaries(min_size=k)):
        return []
    records = [store.get(rid) for rid in store.theme_record_ids(theme_id, limit)]
    return [evidence(r) for r in records if r is not None]


def snapshot(store: Store, *, k: int, evidence_per_theme: int = 6) -> Snapshot:
    theme_list = themes(store, k=k)
    return Snapshot(
        overview=overview(store, k=k),
        themes=theme_list,
        graph=graph(store, k=k),
        evidence={
            t.id: theme_evidence(store, t.id, k=k, limit=evidence_per_theme) for t in theme_list
        },
    )


def static_dir() -> Path:
    return Path(str(resources.files("obsei") / "studio_static"))


def export(
    store: Store, out: Path, *, k: int, demo: bool = False, embedder: str | None = None
) -> None:
    """Write a self-contained static Studio (HTML, JS, CSS and data.json) to ``out``.

    ``demo`` marks the snapshot as synthetic; only ``obsei demo`` sets it, along with the
    ``embedder`` model that grouped the themes.
    """
    out.mkdir(parents=True, exist_ok=True)
    for name in STATIC_FILES:
        shutil.copyfile(static_dir() / name, out / name)
    page = (static_dir() / "index.html").read_text(encoding="utf-8")
    if LIVE_DATA not in page:
        raise RuntimeError("studio_static/index.html has no data source marker")
    (out / "index.html").write_text(page.replace(LIVE_DATA, EXPORT_DATA), encoding="utf-8")
    data = snapshot(store, k=k).model_copy(update={"demo": demo, "embedder": embedder})
    (out / "data.json").write_text(data.model_dump_json(), encoding="utf-8")
