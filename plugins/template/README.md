# obsei-example

An obsei plugin made from the plugin template (`obsei plugin new example`). In the obsei
repository, `plugins/template` is that template: copy it to `plugins/obsei-<name>` or run
`obsei plugin new <name> --dir plugins/obsei-<name>`.

A plugin is a normal Python package whose `obsei.plugins` entry point is a
`register(registry)` hook. Sources implement `fetch(cursor)`, enrichers `enrich(batch)` and sinks
`send(batch)` (see `obsei.core.protocols`); each comes with a pydantic config model whose fields
have descriptions, and a `Catalog` that `obsei integrations` and `obsei add` show.

```bash
pip install -e .           # then allow it in obsei.yaml: plugins: [example]
obsei add example          # asks for its settings and previews a record
pytest
```

Rules for plugins in the obsei repository:

- Typed (mypy strict), tested with mocked HTTP, no network in tests.
- Secrets only through `*_env` config fields marked `json_schema_extra=SECRET`; never log or
  store them.
- Use `ctx.author(handle)` for authors so handles are pseudonymised; never put handles in text,
  context or URLs.
- Respect each platform's terms. Scrapers stay community plugins, opt-in and clearly labelled.

Users enable installed plugins by name in `obsei.yaml` (`plugins: [example]`), so installing a
package never runs its code until it is allowed.
