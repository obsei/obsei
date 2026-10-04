from __future__ import annotations

import json
import os
import platform
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import resources
from itertools import islice
from pathlib import Path
from typing import Annotated

import duckdb
import typer

from obsei import __version__
from obsei.config import (
    DEFAULT_PATH,
    ConfigError,
    ObseiConfig,
    build_context,
    build_pipeline,
    builtin_registry,
    load_config,
)
from obsei.core.record import Record
from obsei.core.registry import PluginError
from obsei.llm import EgressPolicy
from obsei.pipeline import PipelineError
from obsei.pipeline import run as run_pipeline
from obsei.privacy.pseudonym import PseudonymSaltError, load_salt, pseudonymize
from obsei.store import DB_KEY_ENV_VAR, Store, StoreError, load_db_key

app = typer.Typer(
    name="obsei",
    help="Privacy-first, self-hosted Voice of Customer for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"obsei {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
) -> None:
    pass


@app.command()
def version() -> None:
    """Show the obsei version."""
    typer.echo(f"obsei {__version__}")


@app.command()
def doctor() -> None:
    """Check the local environment and list discovered plugins."""
    typer.echo(f"obsei     {__version__}")
    typer.echo(f"python    {platform.python_version()} ({sys.platform})")
    try:
        load_salt()
        salt_status = "configured"
    except PseudonymSaltError:
        salt_status = "not set (OBSEI_PSEUDONYM_SALT is required before ingesting authors)"
    typer.echo(f"salt      {salt_status}")
    try:
        key_status = "configured" if load_db_key() else f"not set ({DB_KEY_ENV_VAR})"
    except StoreError as exc:
        key_status = f"invalid ({exc})"
    typer.echo(f"db key    {key_status}")
    typer.echo(f"duckdb    {duckdb.__version__} (encryption: {_crypto_status()})")
    policy = EgressPolicy.from_env()
    allowed = f" (allow: {', '.join(sorted(policy.allowed_hosts))})" if policy.allowed_hosts else ""
    typer.echo(f"egress    {policy.mode}{allowed}")
    registry = builtin_registry()
    loaded = registry.load_entry_points()
    typer.echo(f"plugins   {', '.join(loaded) if loaded else 'built-in only'}")
    for kind, names in registry.names().items():
        if names:
            typer.echo(f"  {kind:<9}{', '.join(names)}")


def _crypto_status() -> str:
    row = (
        duckdb.connect()
        .execute("SELECT installed FROM duckdb_extensions() WHERE extension_name = 'httpfs'")
        .fetchone()
    )
    if row and row[0]:
        return "ready"
    return "httpfs extension not installed; it is installed on first encrypted write"


@app.command()
def schema() -> None:
    """Print the Feedback Record JSON Schema."""
    typer.echo(json.dumps(Record.model_json_schema(), indent=2, sort_keys=True))


DbOption = Annotated[
    Path, typer.Option("--db", envvar="OBSEI_DB", help="Path to the obsei DuckDB file.")
]
API_TOKEN_ENV_VAR = "OBSEI_API_TOKEN"  # noqa: S105

UnencryptedOption = Annotated[
    bool,
    typer.Option("--unencrypted", help="Open without an encryption key (encrypted disks only)."),
]


def _open_store(db: Path, unencrypted: bool, *, read_only: bool = False) -> Store:
    try:
        return Store(
            db, encryption_key=load_db_key(), allow_unencrypted=unencrypted, read_only=read_only
        )
    except StoreError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None


def _author_pseudonym(handle: str) -> str:
    try:
        return pseudonymize(handle, load_salt())
    except PseudonymSaltError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None


@app.command()
def forget(
    db: DbOption = Path("obsei.duckdb"),
    author: Annotated[str | None, typer.Option(help="Author handle to erase.")] = None,
    source: Annotated[str | None, typer.Option(help="Source type to erase.")] = None,
    instance: Annotated[str | None, typer.Option(help="Source instance (with --source).")] = None,
    older_than_days: Annotated[
        int | None, typer.Option(min=1, help="Erase records created more than N days ago.")
    ] = None,
    unencrypted: UnencryptedOption = False,
) -> None:
    """Erase records by author, source or age (erasure requests and retention)."""
    if author is None and source is None and older_than_days is None:
        typer.echo("error: pass --author, --source or --older-than-days", err=True)
        raise typer.Exit(2)
    before = None
    if older_than_days is not None:
        before = datetime.now(UTC) - timedelta(days=older_than_days)
    with _open_store(db, unencrypted) as store:
        deleted = store.delete(
            author_pseudonym=_author_pseudonym(author) if author else None,
            source_type=source,
            source_instance=instance,
            before=before,
        )
        store.audit(
            "forget",
            {
                "author_pseudonym": _author_pseudonym(author) if author else None,
                "source": source,
                "instance": instance,
                "older_than_days": older_than_days,
                "deleted": deleted,
            },
        )
    typer.echo(f"deleted {deleted} record(s)")


@app.command()
def audit(
    db: DbOption = Path("obsei.duckdb"),
    limit: Annotated[int, typer.Option(min=1)] = 50,
    unencrypted: UnencryptedOption = False,
) -> None:
    """Show the erasure and export log (newest first)."""
    with _open_store(db, unencrypted, read_only=True) as store:
        for at, action, detail in store.audit_log(limit=limit):
            typer.echo(f"{at.isoformat()}  {action:<7} {detail}")


@app.command()
def export(
    author: Annotated[str, typer.Option(help="Author handle whose records to export.")],
    db: DbOption = Path("obsei.duckdb"),
    out: Annotated[
        Path | None, typer.Option(help="Write JSON Lines here (default stdout).")
    ] = None,
    unencrypted: UnencryptedOption = False,
) -> None:
    """Export one author's records as JSON Lines (access requests)."""
    pseudonym = _author_pseudonym(author)
    with _open_store(db, unencrypted) as store:
        lines = [r.model_dump_json() for r in store.iter_records(author_pseudonym=pseudonym)]
        store.audit("export", {"author_pseudonym": pseudonym, "records": len(lines)})
    if out is None:
        for line in lines:
            typer.echo(line)
    else:
        out.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        typer.echo(f"exported {len(lines)} record(s) to {out}", err=True)


ConfigOption = Annotated[
    Path, typer.Option("--config", "-c", envvar="OBSEI_CONFIG", help="Path to obsei.yaml.")
]
PipelineOption = Annotated[
    list[str] | None, typer.Option("--pipeline", "-p", help="Pipeline(s) to use (default all).")
]


def _fail(message: object) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(2)


def _load(config: Path) -> ObseiConfig:
    try:
        return load_config(config)
    except ConfigError as exc:
        raise _fail(exc) from None


@app.command()
def init(
    directory: Annotated[Path, typer.Argument(help="Where to create the project.")] = Path(),
    force: Annotated[bool, typer.Option(help="Overwrite existing files.")] = False,
) -> None:
    """Create obsei.yaml and a multilingual sample dataset."""
    templates = resources.files("obsei") / "templates"
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("obsei.yaml", "feedback.csv"):
        target = directory / name
        if target.exists() and not force:
            typer.echo(f"skip   {target} (exists)")
            continue
        target.write_text((templates / name).read_text(encoding="utf-8"), encoding="utf-8")
        typer.echo(f"create {target}")
    typer.echo(
        "next: export OBSEI_DB_KEY=... OBSEI_PSEUDONYM_SALT=... then 'obsei try' and 'obsei run'"
    )


@app.command()
def run(
    config: ConfigOption = DEFAULT_PATH,
    pipeline: PipelineOption = None,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
    every: Annotated[
        int | None, typer.Option(min=1, help="Repeat every N minutes until stopped.")
    ] = None,
) -> None:
    """Run pipelines: fetch, redact, enrich, deliver and store new or changed feedback."""
    while True:
        _run_once(config, pipeline, db)
        if every is None:
            return
        time.sleep(every * 60)


def _run_once(config: Path, pipeline: list[str] | None, db: Path | None) -> None:
    cfg = _load(config)
    names = pipeline or [p.name for p in cfg.pipelines]
    with (
        build_context(cfg) as ctx,
        _open_store(db or cfg.store.path, cfg.store.unencrypted) as store,
    ):
        for name in names:
            try:
                report = run_pipeline(build_pipeline(cfg, name, ctx), store)
            except (ConfigError, PipelineError, PluginError, OSError, RuntimeError) as exc:
                raise _fail(exc) from None
            sent = ", ".join(f"{k}={v}" for k, v in report.sent.items()) or "none"
            typer.echo(
                f"{name}: fetched {report.fetched}, stored {report.stored}, "
                f"enriched {sum(report.enriched.values())}, sent {sent}"
            )


@app.command("try")
def try_(
    config: ConfigOption = DEFAULT_PATH,
    pipeline: PipelineOption = None,
    limit: Annotated[int, typer.Option(min=1, help="Records per source.")] = 3,
    enrich: Annotated[bool, typer.Option(help="Also run enrichers.")] = False,
) -> None:
    """Preview redacted records from each source. Nothing is stored or sent."""
    cfg = _load(config)
    names = pipeline or [p.name for p in cfg.pipelines]
    with build_context(cfg) as ctx:
        for name in names:
            try:
                built = build_pipeline(cfg, name, ctx, with_sinks=False)
            except (ConfigError, PluginError, OSError, RuntimeError) as exc:
                raise _fail(exc) from None
            for spec in built.sources:
                records = [r for r, _ in islice(spec.source.fetch(None), limit)]
                if built.redactor is not None:
                    records = list(built.redactor.redact(records))
                for enricher in built.enrichers if enrich else ():
                    results = enricher.enrich(records)
                    records = [
                        r if e is None else r.with_enrichment(enricher.name, e)
                        for r, e in zip(records, results, strict=True)
                    ]
                for record in records:
                    typer.echo(
                        record.model_dump_json(
                            include={
                                "source",
                                "text",
                                "created_at",
                                "rating",
                                "lang",
                                "context",
                                "enrichments",
                            }
                        )
                    )


def _store_settings(config: Path, db: Path | None) -> tuple[Path, bool]:
    if config.exists():
        cfg = _load(config)
        return db or cfg.store.path, cfg.store.unencrypted
    return db or Path("obsei.duckdb"), False


@app.command()
def mcp(
    config: ConfigOption = DEFAULT_PATH,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
) -> None:
    """Serve read-only MCP tools over stdio (Claude, ChatGPT, Cursor, your agents)."""
    try:
        from obsei.mcp_server import create_server  # noqa: PLC0415
    except ImportError:
        raise _fail("MCP support needs: pip install 'obsei[mcp]'") from None
    path, unencrypted = _store_settings(config, db)

    @contextmanager
    def read_only() -> Iterator[Store]:
        with _open_store(path, unencrypted, read_only=True) as store:
            yield store

    create_server(read_only).run("stdio")


@app.command()
def serve(
    config: ConfigOption = DEFAULT_PATH,
    host: Annotated[str, typer.Option(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port.")] = 8765,
) -> None:
    """Serve webhook intake (/ingest), MCP over HTTP (/mcp) and /healthz."""
    try:
        import uvicorn  # noqa: PLC0415

        from obsei.serve import create_app  # noqa: PLC0415
    except ImportError:
        raise _fail("serve needs: pip install 'obsei[mcp]'") from None
    token = os.environ.get(API_TOKEN_ENV_VAR) or None
    if token is None and host not in ("127.0.0.1", "::1", "localhost"):
        raise _fail(f"set {API_TOKEN_ENV_VAR} before binding to {host}")
    cfg = _load(config)
    with build_context(cfg) as ctx, _open_store(cfg.store.path, cfg.store.unencrypted) as store:
        try:
            web = create_app(cfg, ctx, store, token=token, host=host)
        except (ConfigError, PluginError, OSError, RuntimeError) as exc:
            raise _fail(exc) from None
        uvicorn.run(web, host=host, port=port, log_level="info")
