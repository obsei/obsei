from collections.abc import Iterable, Iterator
from importlib.metadata import EntryPoint
from typing import ClassVar

import pytest
from pydantic import BaseModel

from obsei import Record
from obsei.core.context import Context
from obsei.core.plugin import factory
from obsei.core.protocols import Cursor
from obsei.core.registry import (
    Discover,
    DuplicatePluginError,
    PluginError,
    PluginNotFoundError,
    Registry,
)


class DummySource:
    name: ClassVar[str] = "dummy"

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        return iter(())


class NoConfig(BaseModel):
    pass


def build_dummy(config: NoConfig, ctx: Context) -> DummySource:
    return DummySource()


DUMMY = factory(NoConfig, build_dummy)


def register_dummy(registry: Registry) -> None:
    registry.add_source("dummy", DUMMY)


def test_add_and_lookup() -> None:
    registry = Registry()
    registry.add_source("dummy", DUMMY)
    assert registry.source("dummy") is DUMMY
    assert registry.names() == {"source": ["dummy"], "enricher": [], "sink": []}


def test_duplicate_requires_replace() -> None:
    registry = Registry()
    registry.add_source("dummy", DUMMY)
    with pytest.raises(DuplicatePluginError):
        registry.add_source("dummy", DUMMY)
    registry.add_source("dummy", DUMMY, replace=True)


def test_missing_plugin() -> None:
    with pytest.raises(PluginNotFoundError):
        Registry().sink("nope")


@pytest.mark.parametrize("name", ["", "a.b", "../x", "os.system"])
def test_invalid_names(name: str) -> None:
    with pytest.raises(PluginError):
        Registry().add_source(name, DUMMY)


def _discover(*eps: EntryPoint) -> Discover:
    def discover(group: str) -> Iterable[EntryPoint]:
        return [ep for ep in eps if ep.group == group]

    return discover


def test_load_entry_points_with_allowlist() -> None:
    good = EntryPoint(name="dummy", value="test_registry:register_dummy", group="obsei.plugins")
    other = EntryPoint(name="other", value="os:system", group="obsei.plugins")
    registry = Registry()
    loaded = registry.load_entry_points(allow={"dummy"}, discover=_discover(good, other))
    assert loaded == ["dummy"]
    assert registry.source("dummy") is DUMMY


def test_entry_point_must_be_callable() -> None:
    bad = EntryPoint(name="bad", value="test_registry:NoConfig.__doc__", group="obsei.plugins")
    with pytest.raises(PluginError):
        Registry().load_entry_points(discover=_discover(bad))
