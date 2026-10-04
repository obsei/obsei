"""Plugin registry.

Plugins are referenced by name only (``type: appstore`` in YAML), never by import
path, so configuration can never import arbitrary code. Third-party plugins
register through the ``obsei.plugins`` entry-point group: each entry point names a
callable ``register(registry: Registry) -> None``.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from importlib.metadata import EntryPoint, entry_points
from typing import Literal, get_args

PluginKind = Literal["source", "enricher", "sink"]
PLUGIN_KINDS: tuple[PluginKind, ...] = get_args(PluginKind)
ENTRY_POINT_GROUP = "obsei.plugins"


class PluginError(Exception):
    """Base error for plugin registration and lookup."""


class PluginNotFoundError(PluginError, KeyError):
    """No plugin of that kind and name is registered."""


class DuplicatePluginError(PluginError):
    """A plugin with the same kind and name is already registered."""


class Registry:
    """Maps (kind, name) to plugin classes."""

    def __init__(self) -> None:
        self._plugins: dict[PluginKind, dict[str, type]] = {kind: {} for kind in PLUGIN_KINDS}
        self.loaded_entry_points: list[str] = []

    def register(self, kind: PluginKind, name: str, plugin: type, *, replace: bool = False) -> None:
        if kind not in self._plugins:
            raise PluginError(f"unknown plugin kind {kind!r}; expected one of {PLUGIN_KINDS}")
        if not name or not name.replace("-", "_").isidentifier():
            raise PluginError(f"invalid plugin name {name!r}")
        if name in self._plugins[kind] and not replace:
            raise DuplicatePluginError(f"{kind} plugin {name!r} is already registered")
        self._plugins[kind][name] = plugin

    def get(self, kind: PluginKind, name: str) -> type:
        try:
            return self._plugins[kind][name]
        except KeyError:
            raise PluginNotFoundError(f"no {kind} plugin named {name!r}") from None

    def names(self, kind: PluginKind) -> list[str]:
        return sorted(self._plugins[kind])

    def load_entry_points(
        self,
        *,
        allow: Collection[str] | None = None,
        group: str = ENTRY_POINT_GROUP,
        discover: Callable[[str], Collection[EntryPoint]] | None = None,
    ) -> list[str]:
        """Load plugin packages from entry points.

        ``allow`` restricts loading to the named entry points; server mode always
        passes an explicit allowlist. Returns the names that were loaded.
        """
        found = discover(group) if discover else entry_points(group=group)
        loaded: list[str] = []
        for ep in sorted(found, key=lambda e: e.name):
            if allow is not None and ep.name not in allow:
                continue
            hook = ep.load()
            if not callable(hook):
                raise PluginError(f"entry point {ep.name!r} does not reference a callable")
            hook(self)
            loaded.append(ep.name)
        self.loaded_entry_points.extend(loaded)
        return loaded
