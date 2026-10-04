---
title: Plugins
description: Write a source, enricher or sink.
---

Plugins are separate packages. Community plugins in this repository's `plugins/` directory are
not published to PyPI; install them from Git, for example:

```bash
pip install "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
```

A plugin exposes a `register(registry)` hook through the `obsei.plugins` entry point and pairs
each component with a pydantic config model:

```python
from obsei.core.plugin import factory
from obsei.core.registry import Registry

def register(registry: Registry) -> None:
    registry.add_source("example", factory(ExampleConfig, ExampleSource))
```

Installed plugins load only when allowed by name in `obsei.yaml` (`plugins: [example]`). Start
from [`plugins/template`](https://github.com/obsei/obsei/tree/master/plugins/template).
