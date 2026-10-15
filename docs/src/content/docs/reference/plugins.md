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

`obsei-teams` is on PyPI; `obsei-reddit` and `obsei-typeform` install from Git:

```bash
pip install obsei-teams
pip install "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
pip install "obsei-typeform @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-typeform"
# uv tool: repeat --with for each plugin, and keep your extras
uv tool install --force obsei --with obsei-teams
```

Each plugin's README lists its configuration. The `teams` sink posts to public Microsoft hosts,
so private egress mode needs them allowed:
`OBSEI_EGRESS_ALLOW=logic.azure.com,environment.api.powerplatform.com`. Complete configurations
are in [`examples/surveys-typeform.yaml`](https://github.com/obsei/obsei/blob/master/examples/surveys-typeform.yaml)
and [`examples/alerts-teams.yaml`](https://github.com/obsei/obsei/blob/master/examples/alerts-teams.yaml).

## Writing a plugin

Start from the template:

```bash
obsei plugin new acme            # creates ./obsei-acme: package obsei_acme, type acme, a test
pip install -e obsei-acme        # then allow it in obsei.yaml: plugins: [acme]
obsei add acme                   # asks for its settings and previews a record
```

In this repository, the template is [`plugins/template`](https://github.com/obsei/obsei/tree/master/plugins/template);
`obsei plugin new acme --dir plugins/obsei-acme` creates a first-party plugin from it.

A plugin exposes a `register(registry)` hook through the `obsei.plugins` entry point:

```toml
[project]
name = "obsei-example"
dependencies = ["obsei>=1.0,<2"]

[project.entry-points."obsei.plugins"]
example = "obsei_example:register"
```

The hook pairs each component with a pydantic config model, which validates the `config` block
in `obsei.yaml`:

```python
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import Context
from obsei.core.plugin import Catalog, factory
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.core.registry import Registry


class ExampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    greeting: str = Field(default="hello", description="Text of the one record this source yields.")


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
    registry.add_source(
        "example",
        factory(
            ExampleConfig,
            ExampleSource,
            Catalog(title="Example", category="data", docs_url="https://github.com/you/obsei-example"),
        ),
    )
```

The `Catalog` is what `obsei integrations` and `obsei add` show: a `title`, a `category`
(reviews, support, social, surveys, data, chat, issues, warehouse or notify), a `status` (`beta`
until a live test covers it), `docs_url`, and `help_url`, the provider's page on getting the
credential. Give every config field a `description`: `obsei add` shows it at each prompt and
editors show it on hover. Mark each `*_env` field that names a secret with
`json_schema_extra=SECRET` (from `obsei.core.plugin`), so `obsei add` asks for the value hidden and
stores it in `.obsei/secrets.env`:

```python
token_env: str = Field(
    default="ACME_TOKEN", description="Environment variable with an Acme API token.",
    json_schema_extra=SECRET,
)
```

Sinks can also implement `verify()`, which checks credentials and the target without delivering
anything; `obsei add` and `obsei check` call it.

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
