"""Embedding, theme and graph queries over the store (mixed into ``Store``)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import duckdb

_SIMILAR = "list_cosine_similarity({col}, CAST(? AS FLOAT[]))"
PEOPLE = "count(DISTINCT coalesce({p}author_pseudonym, {p}id))"
"""k-anonymity counts people: distinct author pseudonyms, records without an author count alone."""
_PEOPLE = PEOPLE.format(p="r.")
_RATING = "CAST(json_extract_string(r.data, '$.rating') AS DOUBLE)"


def _vec(vector: list[float]) -> str:
    """DuckDB binds Python float lists slowly; a text literal cast in SQL is much faster."""
    return json.dumps(vector)


@dataclass(frozen=True)
class ThemeSummary:
    id: str
    label: str | None
    description: str | None
    size: int
    duplicates: int
    avg_rating: float | None
    last_7_days: int
    previous_7_days: int
    sources: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    intents: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str
    label: str
    weight: int


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    weight: int


@dataclass(frozen=True)
class Graph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


_FACETS: dict[str, str] = {
    "source": "r.source_type",
    "lang": "coalesce(json_extract_string(r.data, '$.lang'), "
    "json_extract_string(r.data, '$.enrichments.classify.value.language'))",
    "intent": "json_extract_string(r.data, '$.enrichments.classify.value.intent')",
    "sentiment": "json_extract_string(r.data, '$.enrichments.classify.value.sentiment')",
}


class ThemeQueries:
    _con: duckdb.DuckDBPyConnection

    def pending_embeddings(self, model: str, limit: int) -> list[tuple[str, str, str]]:
        """(id, content_hash, text) of records without a current embedding for ``model``."""
        rows = self._con.execute(
            "SELECT r.id, r.content_hash, json_extract_string(r.data, '$.text') FROM records r "
            "LEFT JOIN embeddings e ON e.record_id = r.id "
            "WHERE e.record_id IS NULL OR e.model != ? OR e.content_hash != r.content_hash "
            "ORDER BY r.created_at LIMIT ?",
            [model, limit],
        ).fetchall()
        return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]

    def put_embeddings(self, rows: list[tuple[str, str, str, list[float]]]) -> None:
        """Upsert (id, model, content_hash, vector); changed records lose their theme."""
        if not rows:
            return
        ids = [r[0] for r in rows]
        self._unassign(ids)
        self._con.execute("DELETE FROM embeddings WHERE list_contains(?, record_id)", [ids])
        self._con.executemany(
            "INSERT INTO embeddings VALUES (?, ?, ?, CAST(? AS FLOAT[]))",
            [(rid, model, digest, _vec(vector)) for rid, model, digest, vector in rows],
        )

    def _unassign(self, ids: list[str]) -> None:
        """Remove records from their themes and recompute those themes from what remains."""
        affected = [
            str(r[0])
            for r in self._con.execute(
                "SELECT DISTINCT theme_id FROM record_themes WHERE list_contains(?, record_id)",
                [ids],
            ).fetchall()
        ]
        self._con.execute("DELETE FROM record_themes WHERE list_contains(?, record_id)", [ids])
        self._con.execute(
            "UPDATE record_themes SET duplicate_of = NULL WHERE list_contains(?, duplicate_of)",
            [ids],
        )
        self._recenter(affected, exclude=ids)

    def _recenter(self, theme_ids: list[str], *, exclude: list[str]) -> None:
        if not theme_ids:
            return
        members: dict[str, list[list[float]]] = {t: [] for t in theme_ids}
        for theme_id, vector in self._con.execute(
            "SELECT t.theme_id, e.vector FROM record_themes t "
            "JOIN embeddings e ON e.record_id = t.record_id "
            "WHERE list_contains(?, t.theme_id) AND NOT list_contains(?, t.record_id)",
            [theme_ids, exclude],
        ).fetchall():
            members[str(theme_id)].append([float(v) for v in vector])
        now = datetime.now(UTC)
        for theme_id, vectors in members.items():
            if not vectors:
                self._con.execute("DELETE FROM themes WHERE id = ?", [theme_id])
                continue
            mean = [sum(col) / len(vectors) for col in zip(*vectors, strict=True)]
            norm = sum(v * v for v in mean) ** 0.5 or 1.0
            self._con.execute(
                "UPDATE themes SET centroid = CAST(? AS FLOAT[]), size = ?, updated_at = ? "
                "WHERE id = ?",
                [_vec([v / norm for v in mean]), len(vectors), now, theme_id],
            )

    def unassigned(self, model: str, limit: int) -> list[tuple[str, list[float]]]:
        rows = self._con.execute(
            "SELECT e.record_id, e.vector FROM embeddings e JOIN records r ON r.id = e.record_id "
            "LEFT JOIN record_themes t ON t.record_id = e.record_id "
            "WHERE t.record_id IS NULL AND e.model = ? ORDER BY r.created_at, r.id LIMIT ?",
            [model, limit],
        ).fetchall()
        return [(str(r[0]), [float(v) for v in r[1]]) for r in rows]

    def nearest_theme(self, vector: list[float], model: str) -> tuple[str, float] | None:
        row = self._con.execute(
            f"SELECT id, {_SIMILAR.format(col='centroid')} AS s FROM themes "  # noqa: S608
            "WHERE model = ? ORDER BY s DESC LIMIT 1",
            [_vec(vector), model],
        ).fetchone()
        return (str(row[0]), float(row[1])) if row and row[1] is not None else None

    def nearest_record(self, vector: list[float], model: str) -> tuple[str, float] | None:
        """Most similar record that already has a theme."""
        row = self._con.execute(
            f"SELECT e.record_id, {_SIMILAR.format(col='e.vector')} AS s "  # noqa: S608
            "FROM embeddings e JOIN record_themes t ON t.record_id = e.record_id "
            "WHERE e.model = ? ORDER BY s DESC LIMIT 1",
            [_vec(vector), model],
        ).fetchone()
        return (str(row[0]), float(row[1])) if row and row[1] is not None else None

    def theme_centroid(self, theme_id: str) -> tuple[list[float], int]:
        row = self._con.execute(
            "SELECT centroid, size FROM themes WHERE id = ?", [theme_id]
        ).fetchone()
        if row is None:
            raise KeyError(theme_id)
        return [float(v) for v in row[0]], int(row[1])

    def save_theme(self, theme_id: str, model: str, centroid: list[float], size: int) -> None:
        now = datetime.now(UTC)
        self._con.execute(
            "INSERT INTO themes VALUES (?, ?, NULL, NULL, CAST(? AS FLOAT[]), ?, ?, ?) "
            "ON CONFLICT (id) "
            "DO UPDATE SET centroid = excluded.centroid, size = excluded.size, "
            "updated_at = excluded.updated_at",
            [theme_id, model, _vec(centroid), size, now, now],
        )

    def assign(
        self, record_id: str, theme_id: str, similarity: float, duplicate_of: str | None
    ) -> None:
        self._con.execute(
            "INSERT INTO record_themes VALUES (?, ?, ?, ?)",
            [record_id, theme_id, similarity, duplicate_of],
        )

    def unlabeled_themes(self, min_size: int) -> list[str]:
        """Unlabelled themes with at least ``min_size`` distinct people."""
        rows = self._con.execute(
            "SELECT th.id FROM themes th JOIN record_themes t ON t.theme_id = th.id "  # noqa: S608
            "JOIN records r ON r.id = t.record_id WHERE th.label IS NULL "
            f"GROUP BY th.id, th.size HAVING {_PEOPLE} >= ? ORDER BY th.size DESC, th.id",
            [min_size],
        ).fetchall()
        return [str(r[0]) for r in rows]

    def theme_samples(self, theme_id: str, limit: int = 8) -> list[str]:
        rows = self._con.execute(
            "SELECT json_extract_string(r.data, '$.text') FROM record_themes t "
            "JOIN records r ON r.id = t.record_id "
            "WHERE t.theme_id = ? AND t.duplicate_of IS NULL ORDER BY t.similarity DESC LIMIT ?",
            [theme_id, limit],
        ).fetchall()
        return [str(r[0]) for r in rows]

    def label_theme(self, theme_id: str, label: str, description: str | None) -> None:
        self._con.execute(
            "UPDATE themes SET label = ?, description = ? WHERE id = ?",
            [label, description, theme_id],
        )

    def _facet(
        self, facet: str, theme_ids: list[str], min_people: int
    ) -> dict[str, dict[str, int]]:
        """Record counts per facet value, leaving out values from fewer than ``min_people``."""
        rows = self._con.execute(
            f"SELECT t.theme_id, {_FACETS[facet]} AS k, count(*) FROM record_themes t "  # noqa: S608
            "JOIN records r ON r.id = t.record_id WHERE list_contains(?, t.theme_id) "
            f"AND k IS NOT NULL GROUP BY ALL HAVING {_PEOPLE} >= ? ORDER BY 3 DESC",
            [theme_ids, min_people],
        ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for theme_id, key, count in rows:
            result.setdefault(str(theme_id), {})[str(key)] = int(count)
        return result

    def theme_summaries(
        self, *, min_size: int = 1, now: datetime | None = None
    ) -> list[ThemeSummary]:
        """Themes from at least ``min_size`` people (k-anonymity), largest first. Facet values
        and average ratings from fewer than ``min_size`` people are left out."""
        moment = now or datetime.now(UTC)
        week, fortnight = moment - timedelta(days=7), moment - timedelta(days=14)
        rows = self._con.execute(
            "SELECT th.id, th.label, th.description, th.size, "  # noqa: S608
            f"count(t.duplicate_of), CASE WHEN {_PEOPLE} FILTER (WHERE {_RATING} IS NOT NULL) "
            f">= ? THEN avg({_RATING}) END, "
            "count(*) FILTER (WHERE r.created_at >= ?), "
            "count(*) FILTER (WHERE r.created_at >= ? AND r.created_at < ?) "
            "FROM themes th JOIN record_themes t ON t.theme_id = th.id "
            "JOIN records r ON r.id = t.record_id "
            f"GROUP BY th.id, th.label, th.description, th.size HAVING {_PEOPLE} >= ? "
            "ORDER BY th.size DESC, th.id",
            [min_size, week, fortnight, week, min_size],
        ).fetchall()
        ids = [str(r[0]) for r in rows]
        sources, languages, intents = (
            self._facet(f, ids, min_size) for f in ("source", "lang", "intent")
        )
        return [
            ThemeSummary(
                id=str(r[0]),
                label=r[1],
                description=r[2],
                size=int(r[3]),
                duplicates=int(r[4]),
                avg_rating=r[5],
                last_7_days=int(r[6]),
                previous_7_days=int(r[7]),
                sources=sources.get(str(r[0]), {}),
                languages=languages.get(str(r[0]), {}),
                intents=intents.get(str(r[0]), {}),
            )
            for r in rows
        ]

    def theme_record_ids(self, theme_id: str, limit: int) -> list[str]:
        rows = self._con.execute(
            "SELECT record_id FROM record_themes WHERE theme_id = ? AND duplicate_of IS NULL "
            "ORDER BY similarity DESC LIMIT ?",
            [theme_id, limit],
        ).fetchall()
        return [str(r[0]) for r in rows]

    def similar_records(
        self, vector: list[float], model: str, limit: int
    ) -> list[tuple[str, float]]:
        rows = self._con.execute(
            f"SELECT record_id, {_SIMILAR.format(col='vector')} AS s FROM embeddings "  # noqa: S608
            "WHERE model = ? ORDER BY s DESC LIMIT ?",
            [_vec(vector), model, limit],
        ).fetchall()
        return [(str(r[0]), float(r[1])) for r in rows]

    def graph(self, *, min_size: int = 1) -> Graph:
        """Themes linked to sources, languages, intents and sentiments, with record counts.

        Links from fewer than ``min_size`` people are left out."""
        themes = self.theme_summaries(min_size=min_size)
        ids = [t.id for t in themes]
        nodes: dict[str, GraphNode] = {
            t.id: GraphNode(t.id, "theme", t.label or t.id, t.size) for t in themes
        }
        edges: list[GraphEdge] = []
        for facet in _FACETS:
            totals: dict[str, int] = {}
            for theme_id, counts in self._facet(facet, ids, min_size).items():
                for key, count in counts.items():
                    node_id = f"{facet}:{key}"
                    totals[node_id] = totals.get(node_id, 0) + count
                    edges.append(GraphEdge(theme_id, node_id, count))
            for node_id, total in totals.items():
                nodes[node_id] = GraphNode(node_id, facet, node_id.split(":", 1)[1], total)
        return Graph(nodes=list(nodes.values()), edges=edges)
