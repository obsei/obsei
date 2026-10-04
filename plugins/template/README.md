# Plugin template

Copy this directory to `plugins/obsei-<name>`, rename `obsei_example`, and edit `pyproject.toml`.
A plugin is a normal Python package whose `obsei.plugins` entry point is a
`register(registry)` hook. Sources implement `fetch(cursor)`, enrichers `enrich(batch)` and sinks
`send(batch)` (see `obsei.core.protocols`); each comes with a pydantic config model.

Rules for plugins in this repository:

- Typed (mypy strict), tested with mocked HTTP, no network in tests.
- Secrets only through `*_env` config fields; never log or store them.
- Use `ctx.author(handle)` for authors so handles are pseudonymised; never put handles in text,
  context or URLs.
- Respect each platform's terms. Scrapers stay community plugins, opt-in and clearly labelled.

Users enable installed plugins by name in `obsei.yaml` (`plugins: [example]`), so installing a
package never runs its code until it is allowed.
