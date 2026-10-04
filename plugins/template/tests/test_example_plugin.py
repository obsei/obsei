from obsei.core.context import Context
from obsei.core.registry import Registry
from obsei_example import register


def test_example_source_yields_greeting() -> None:
    registry = Registry()
    register(registry)
    source = registry.source("example").create({"greeting": "hi"}, Context())
    ((record, cursor),) = list(source.fetch(None))
    assert record.source.type == "example"
    assert record.text == "hi"
    assert cursor == {"done": True}
