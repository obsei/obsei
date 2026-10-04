---
title: Plugins
description: Write a source, enricher or sink.
---

Plugins live in this repository under `plugins/` and are published as separate packages. A plugin
exposes a `register(registry)` hook through the `obsei.plugins` entry point and pairs each
component with a pydantic config model:

```python
from obsei.core.plugin import factory
from obsei.core.registry import Registry

def register(registry: Registry) -> None:
    registry.add_source("example", factory(ExampleConfig, ExampleSource))
```

Installed plugins load only when allowed by name in `obsei.yaml` (`plugins: [example]`). Start
from [`plugins/template`](https://github.com/obsei/obsei/tree/master/plugins/template).
