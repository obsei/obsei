"""Plugins are looked up by name only, so configuration can never import arbitrary code.

Third-party packages register through the ``obsei.plugins`` entry-point group, whose
value is a ``register(registry: Registry) -> None`` hook.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import Literal, TypeAlias, TypeVar

from obsei.core.protocols import Enricher, Sink, Source

PluginKind: TypeAlias = Literal["source", "enricher", "sink"]
ENTRY_POINT_GROUP = "obsei.plugins"

_P = TypeVar("_P", type[Source], type[Enricher], type[Sink])
RegisterHook: TypeAlias = Callable[["Registry"], None]
Discover: TypeAlias = Callable[[str], Iterable[EntryPoint]]


class PluginError(Exception):
    pass


class PluginNotFoundError(PluginError, KeyError):
    pass


class DuplicatePluginError(PluginError):
    pass


def _add(table: dict[str, _P], kind: PluginKind, name: str, plugin: _P, replace: bool) -> None:
    if not name or not name.replace("-", "_").isidentifier():
        raise PluginError(f"invalid plugin name {name!r}")
    if name in table and not replace:
        raise DuplicatePluginError(f"{kind} plugin {name!r} is already registered")
    table[name] = plugin


def _get(table: dict[str, _P], kind: PluginKind, name: str) -> _P:
    try:
        return table[name]
    except KeyError:
        raise PluginNotFoundError(f"no {kind} plugin named {name!r}") from None


class Registry:
    def __init__(self) -> None:
        self._sources: dict[str, type[Source]] = {}
        self._enrichers: dict[str, type[Enricher]] = {}
        self._sinks: dict[str, type[Sink]] = {}
        self.loaded_entry_points: list[str] = []

    def add_source(self, name: str, plugin: type[Source], *, replace: bool = False) -> None:
        _add(self._sources, "source", name, plugin, replace)

    def add_enricher(self, name: str, plugin: type[Enricher], *, replace: bool = False) -> None:
        _add(self._enrichers, "enricher", name, plugin, replace)

    def add_sink(self, name: str, plugin: type[Sink], *, replace: bool = False) -> None:
        _add(self._sinks, "sink", name, plugin, replace)

    def source(self, name: str) -> type[Source]:
        return _get(self._sources, "source", name)

    def enricher(self, name: str) -> type[Enricher]:
        return _get(self._enrichers, "enricher", name)

    def sink(self, name: str) -> type[Sink]:
        return _get(self._sinks, "sink", name)

    def names(self) -> dict[PluginKind, list[str]]:
        return {
            "source": sorted(self._sources),
            "enricher": sorted(self._enrichers),
            "sink": sorted(self._sinks),
        }

    def load_entry_points(
        self,
        *,
        allow: Collection[str] | None = None,
        group: str = ENTRY_POINT_GROUP,
        discover: Discover | None = None,
    ) -> list[str]:
        """Load plugin hooks; ``allow`` restricts loading to the named entry points."""
        found = discover(group) if discover else entry_points(group=group)
        loaded: list[str] = []
        for ep in sorted(found, key=lambda e: e.name):
            if allow is not None and ep.name not in allow:
                continue
            hook: object = ep.load()
            if not callable(hook):
                raise PluginError(f"entry point {ep.name!r} does not reference a callable")
            hook(self)
            loaded.append(ep.name)
        self.loaded_entry_points.extend(loaded)
        return loaded
