from collections.abc import Collection
from importlib.metadata import EntryPoint
from typing import Any

import pytest

from obsei.core.registry import (
    DuplicatePluginError,
    PluginError,
    PluginNotFoundError,
    Registry,
)


class DummySource:
    name = "dummy"


def register_dummy(registry: Registry) -> None:
    registry.register("source", "dummy", DummySource)


def test_register_and_get() -> None:
    registry = Registry()
    registry.register("source", "dummy", DummySource)
    assert registry.get("source", "dummy") is DummySource
    assert registry.names("source") == ["dummy"]
    assert registry.names("sink") == []


def test_duplicate_requires_replace() -> None:
    registry = Registry()
    registry.register("source", "dummy", DummySource)
    with pytest.raises(DuplicatePluginError):
        registry.register("source", "dummy", DummySource)
    registry.register("source", "dummy", DummySource, replace=True)


def test_missing_plugin() -> None:
    with pytest.raises(PluginNotFoundError):
        Registry().get("sink", "nope")


@pytest.mark.parametrize("name", ["", "a.b", "../x", "os.system"])
def test_invalid_names(name: str) -> None:
    with pytest.raises(PluginError):
        Registry().register("source", name, DummySource)


def test_unknown_kind() -> None:
    with pytest.raises(PluginError):
        Registry().register("transformer", "x", DummySource)  # type: ignore[arg-type]


def _discover(*eps: EntryPoint) -> Any:
    def discover(group: str) -> Collection[EntryPoint]:
        return [ep for ep in eps if ep.group == group]

    return discover


def test_load_entry_points_with_allowlist() -> None:
    good = EntryPoint(name="dummy", value="test_registry:register_dummy", group="obsei.plugins")
    other = EntryPoint(name="other", value="os:system", group="obsei.plugins")
    registry = Registry()
    loaded = registry.load_entry_points(allow={"dummy"}, discover=_discover(good, other))
    assert loaded == ["dummy"]
    assert registry.get("source", "dummy") is DummySource


def test_entry_point_must_be_callable() -> None:
    bad = EntryPoint(name="bad", value="test_registry:DummySource.name", group="obsei.plugins")
    with pytest.raises(PluginError):
        Registry().load_entry_points(discover=_discover(bad))
