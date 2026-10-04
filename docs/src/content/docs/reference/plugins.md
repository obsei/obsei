---
title: Plugins
description: First-party plugins, and how to write a source, enricher or sink.
---

Plugins are separate Python packages. Installing one never runs its code: obsei loads an
installed plugin only when `obsei.yaml` allows it by name.

```yaml
plugins: [typeform, teams]
```

## First-party plugins

These live in the repository's [`plugins/`](https://github.com/obsei/obsei/tree/master/plugins)
directory and are tested with obsei in CI.

| Plugin | Type | Kind | What it does |
|---|---|---|---|
| [`obsei-reddit`](https://github.com/obsei/obsei/tree/master/plugins/obsei-reddit) | `reddit` | source | Subreddit posts, comments and searches from Reddit's public RSS feeds, no API key. |
| [`obsei-typeform`](https://github.com/obsei/obsei/tree/master/plugins/obsei-typeform) | `typeform` | source | Completed Typeform survey responses through the Responses API with your token, incremental; picks text, rating, language and an optional pseudonymised respondent id from chosen fields. |
| [`obsei-teams`](https://github.com/obsei/obsei/tree/master/plugins/obsei-teams) | `teams` | sink | Posts matching, redacted feedback to a Microsoft Teams channel as an Adaptive Card through a Power Automate Workflows webhook. |

Install a plugin from PyPI once it is published, for example:

```bash
pip install obsei-typeform
```

Until then, install it from Git:

```bash
pip install "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
pip install "obsei-typeform @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-typeform"
pip install "obsei-teams @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-teams"
```

Each plugin's README lists its configuration. The `teams` sink posts to public Microsoft hosts,
so private egress mode needs them allowed:
`OBSEI_EGRESS_ALLOW=logic.azure.com,environment.api.powerplatform.com`. Complete configurations
are in [`examples/surveys-typeform.yaml`](https://github.com/obsei/obsei/blob/master/examples/surveys-typeform.yaml)
and [`examples/alerts-teams.yaml`](https://github.com/obsei/obsei/blob/master/examples/alerts-teams.yaml).

## Writing a plugin

Start from [`plugins/template`](https://github.com/obsei/obsei/tree/master/plugins/template):
copy it to `plugins/obsei-<name>`, rename the `obsei_example` package and edit `pyproject.toml`.

A plugin exposes a `register(registry)` hook through the `obsei.plugins` entry point:

```toml
[project]
name = "obsei-example"
dependencies = ["obsei>=1.0.0rc1,<2"]

[project.entry-points."obsei.plugins"]
example = "obsei_example:register"
```

The hook pairs each component with a pydantic config model, which validates the `config` block
in `obsei.yaml`:

```python
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from obsei.core.context import Context
from obsei.core.plugin import factory
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.core.registry import Registry


class ExampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    greeting: str = "hello"


class ExampleSource:
    name: ClassVar[str] = "example"

    def __init__(self, config: ExampleConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        record = Record(
            source=SourceRef(type=self.name, native_id="1"),
            text=self.config.greeting,
            created_at=datetime.now(UTC),
        )
        yield record, {"done": True}


def register(registry: Registry) -> None:
    registry.add_source("example", factory(ExampleConfig, ExampleSource))
```

The protocols live in `obsei.core.protocols`:

- **Sources** implement `fetch(cursor)` and yield `(record, cursor)` pairs. obsei stores the
  cursor of the last record of each batch once every sink accepted it and passes it back on the
  next run, so make each yielded cursor a safe place to resume from.
- **Enrichers** implement `enrich(batch)` and return one `Enrichment` or `None` per record,
  with `name` and `version` class attributes.
- **Sinks** implement `send(batch)` and return a `SinkResult`. They must be idempotent by
  `Record.id`.

Use the `Context` passed to the constructor rather than your own clients:

- `ctx.http` for HTTP. A sink that carries feedback out marks its requests with
  `extensions=EGRESS` (from `obsei.core.context`) and calls `ctx.egress.check(url)` when it is
  created, so the egress policy covers every hop.
- `ctx.author(handle)` for authors, so handles are pseudonymised (or dropped without a salt).
  Never put handles in text, context or URLs.
- `ctx.chat(name)` and `ctx.embedder(name)` for the model endpoints configured under `llms`.

Rules for plugins in this repository:

- Typed (mypy strict) and tested with `httpx.MockTransport`; no network in tests.
- Secrets only through `*_env` config fields; never log or store them.
- Respect each platform's terms. Scrapers stay opt-in and clearly labelled.
