from __future__ import annotations

import json
import os
import platform
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from itertools import islice
from pathlib import Path
from typing import Annotated

import duckdb
import typer

from obsei import __version__, studio
from obsei.ask import ask as ask_feedback
from obsei.config import (
    DEFAULT_PATH,
    ConfigError,
    ObseiConfig,
    StoreConfig,
    build_context,
    build_pipeline,
    builtin_registry,
    load_config,
)
from obsei.core.context import Context, LlmEndpoint
from obsei.core.protocols import Drops
from obsei.core.record import Record
from obsei.core.registry import PluginError
from obsei.demo import (
    DECISION_MODEL,
    decision_labels,
    demo_records,
    demo_snapshot,
    raw_demo_records,
    redacted_demo_records,
    write_labels,
)
from obsei.llm import EgressPolicy
from obsei.llm.client import LlmError, LlmUnreachableError
from obsei.llm.embed import LOCAL_MODEL, MODELS_DIR_ENV, LocalEmbedder
from obsei.privacy.pseudonym import PseudonymSaltError, load_salt, pseudonymize
from obsei.runner import run_pipelines
from obsei.store import (
    DB_KEY_ENV_VAR,
    EXTENSIONS_ENV_VAR,
    INSTALL_HINT,
    PREINSTALL_HINT,
    Store,
    StoreError,
    httpfs_installed,
    install_httpfs,
    load_db_key,
)
from obsei.themes import ThemesConfig, update_themes

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
    policy = EgressPolicy.from_env()
    typer.echo(f"duckdb    {duckdb.__version__} (encryption: {_crypto_status(policy)})")
    allowed = f" (allow: {', '.join(sorted(policy.allowed_hosts))})" if policy.allowed_hosts else ""
    typer.echo(f"egress    {policy.mode}{allowed}")
    registry = builtin_registry()
    loaded = registry.load_entry_points()
    typer.echo(f"plugins   {', '.join(loaded) if loaded else 'built-in only'}")
    for kind, names in registry.names().items():
        if names:
            typer.echo(f"  {kind:<9}{', '.join(names)}")


def _crypto_status(policy: EgressPolicy) -> str:
    directory = os.environ.get(EXTENSIONS_ENV_VAR)
    where = f" in {directory}" if directory else ""
    if httpfs_installed():
        return f"ready, httpfs{where}"
    if policy.mode == "air_gapped":
        return (
            f"httpfs extension not installed{where}; air-gapped mode never downloads it: "
            f"{INSTALL_HINT}; offline, {PREINSTALL_HINT}"
        )
    return "httpfs extension not installed; it is installed on first encrypted write"


@app.command()
def schema() -> None:
    """Print the Feedback Record JSON Schema."""
    typer.echo(json.dumps(Record.model_json_schema(), indent=2, sort_keys=True))


DbOption = Annotated[
    Path | None,
    typer.Option("--db", envvar="OBSEI_DB", help="DuckDB file (default: store.path in config)."),
]
ConfigOption = Annotated[
    Path, typer.Option("--config", "-c", envvar="OBSEI_CONFIG", help="Path to obsei.yaml.")
]
API_TOKEN_ENV_VAR = "OBSEI_API_TOKEN"  # noqa: S105

UnencryptedOption = Annotated[
    bool,
    typer.Option("--unencrypted", help="Open without an encryption key (encrypted disks only)."),
]


def _fail(message: object) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(2)


def _load(config: Path) -> ObseiConfig:
    try:
        return load_config(config)
    except ConfigError as exc:
        raise _fail(exc) from None


def _open_store(
    db: Path,
    unencrypted: bool,
    *,
    read_only: bool = False,
    egress: EgressPolicy | None = None,
    must_exist: bool = False,
) -> Store:
    """Air-gapped egress never downloads DuckDB extensions."""
    if must_exist and not db.exists():
        raise _fail(f"no obsei store at {db}; pass --config or --db")
    mode = (egress or EgressPolicy.from_env()).mode
    try:
        return Store(
            db,
            encryption_key=load_db_key(),
            allow_unencrypted=unencrypted,
            read_only=read_only,
            install_extensions=mode != "air_gapped",
        )
    except StoreError as exc:
        raise _fail(exc) from None


@dataclass(frozen=True)
class StoreSettings:
    path: Path
    unencrypted: bool
    egress: EgressPolicy
    k_anonymity: int


def _store_settings(config: Path, db: Path | None, unencrypted: bool = False) -> StoreSettings:
    """From the config when it exists (an explicit missing ``--config`` is an error); ``--db``
    overrides ``store.path``."""
    if config.exists() or config != DEFAULT_PATH:
        cfg = _load(config)
        return StoreSettings(
            db or cfg.store.path,
            unencrypted or cfg.store.unencrypted,
            cfg.egress or EgressPolicy.from_env(),
            cfg.themes.k_anonymity,
        )
    return StoreSettings(
        db or StoreConfig().path, unencrypted, EgressPolicy.from_env(), ThemesConfig().k_anonymity
    )


def _open_existing(settings: StoreSettings, *, read_only: bool = False) -> Store:
    return _open_store(
        settings.path,
        settings.unencrypted,
        read_only=read_only,
        egress=settings.egress,
        must_exist=True,
    )


def _author_pseudonym(handle: str) -> str:
    try:
        return pseudonymize(handle, load_salt())
    except PseudonymSaltError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None


@app.command()
def forget(
    config: ConfigOption = DEFAULT_PATH,
    db: DbOption = None,
    author: Annotated[str | None, typer.Option(help="Author handle to erase.")] = None,
    source: Annotated[str | None, typer.Option(help="Source type to erase.")] = None,
    instance: Annotated[str | None, typer.Option(help="Source instance (with --source).")] = None,
    older_than_days: Annotated[
        int | None, typer.Option(min=1, help="Erase records created more than N days ago.")
    ] = None,
    unencrypted: UnencryptedOption = False,
) -> None:
    """Erase records by author, source or age (erasure requests and retention).

    Erased records and authors are remembered (by record id and pseudonym) and never stored
    again."""
    if author is None and source is None and older_than_days is None:
        typer.echo("error: pass --author, --source or --older-than-days", err=True)
        raise typer.Exit(2)
    before = None
    if older_than_days is not None:
        before = datetime.now(UTC) - timedelta(days=older_than_days)
    settings = _store_settings(config, db, unencrypted)
    with _open_existing(settings) as store:
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
    config: ConfigOption = DEFAULT_PATH,
    db: DbOption = None,
    limit: Annotated[int, typer.Option(min=1)] = 50,
    unencrypted: UnencryptedOption = False,
) -> None:
    """Show the erasure and export log (newest first)."""
    with _open_existing(_store_settings(config, db, unencrypted), read_only=True) as store:
        for at, action, detail in store.audit_log(limit=limit):
            typer.echo(f"{at.isoformat()}  {action:<7} {detail}")


@app.command()
def export(
    author: Annotated[str, typer.Option(help="Author handle whose records to export.")],
    config: ConfigOption = DEFAULT_PATH,
    db: DbOption = None,
    out: Annotated[
        Path | None, typer.Option(help="Write JSON Lines here (default stdout).")
    ] = None,
    unencrypted: UnencryptedOption = False,
) -> None:
    """Export one author's records as JSON Lines (access requests)."""
    pseudonym = _author_pseudonym(author)
    with _open_existing(_store_settings(config, db, unencrypted)) as store:
        lines = [r.model_dump_json() for r in store.iter_records(author_pseudonym=pseudonym)]
        store.audit("export", {"author_pseudonym": pseudonym, "records": len(lines)})
    if out is None:
        for line in lines:
            typer.echo(line)
    else:
        out.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        typer.echo(f"exported {len(lines)} record(s) to {out}", err=True)


PipelineOption = Annotated[
    list[str] | None, typer.Option("--pipeline", "-p", help="Pipeline(s) to use (default all).")
]


@app.command()
def init(
    directory: Annotated[Path, typer.Argument(help="Where to create the project.")] = Path(),
    force: Annotated[bool, typer.Option(help="Overwrite existing files.")] = False,
    offline: Annotated[
        bool, typer.Option(help="Skip downloading DuckDB's httpfs extension (for encryption).")
    ] = False,
) -> None:
    """Create obsei.yaml and a sample dataset, and install DuckDB's encryption extension."""
    templates = resources.files("obsei") / "templates"
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("obsei.yaml", "feedback.csv"):
        target = directory / name
        if target.exists() and not force:
            typer.echo(f"skip   {target} (exists)")
            continue
        target.write_text((templates / name).read_text(encoding="utf-8"), encoding="utf-8")
        typer.echo(f"create {target}")
    if not offline:
        _install_encryption()
    typer.echo(
        "next: export OBSEI_DB_KEY=... OBSEI_PSEUDONYM_SALT=... then 'obsei try' and 'obsei run'"
    )


def _install_encryption() -> None:
    """Fetch DuckDB's own httpfs extension once; a failure only warns."""
    if httpfs_installed():
        typer.echo("ready  encryption (DuckDB httpfs extension)")
        return
    try:
        install_httpfs()
    except duckdb.Error as exc:
        typer.echo(
            f"warn   could not install DuckDB's httpfs extension, needed for encryption ({exc}); "
            f"{PREINSTALL_HINT}",
            err=True,
        )
        return
    typer.echo("install encryption: DuckDB's httpfs extension (none of your data is sent)")


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
        failed = _run_once(config, pipeline, db)
        if every is None:
            if failed:
                raise typer.Exit(1)
            return
        time.sleep(every * 60)


def _run_once(config: Path, pipeline: list[str] | None, db: Path | None) -> bool:
    """Run every pipeline even when one fails; return whether any failed."""
    cfg = _load(config)
    names = pipeline or [p.name for p in cfg.pipelines]
    with (
        build_context(cfg) as ctx,
        _open_store(db or cfg.store.path, cfg.store.unencrypted, egress=ctx.egress) as store,
    ):
        outcomes = run_pipelines(cfg, ctx, store, names)
    for outcome in outcomes:
        typer.echo(outcome.summary(), err=not outcome.ok)
        for warning in outcome.warnings():
            typer.echo(f"warning: {warning}", err=True)
    return not all(o.ok for o in outcomes)


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
                    if isinstance(enricher, Drops):
                        kept = [r for r in records if enricher.keep(r)]
                        if len(kept) < len(records):
                            typer.echo(
                                f"{name}/{spec.key}: {enricher.name} dropped "
                                f"{len(records) - len(kept)} record(s)",
                                err=True,
                            )
                        records = kept
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
    settings = _store_settings(config, db)

    @contextmanager
    def read_only() -> Iterator[Store]:
        with _open_store(settings.path, settings.unencrypted, read_only=True) as store:
            yield store

    create_server(read_only, k_anonymity=settings.k_anonymity).run("stdio")


@app.command()
def serve(
    config: ConfigOption = DEFAULT_PATH,
    host: Annotated[str, typer.Option(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port.")] = 8765,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
) -> None:
    """Serve webhook intake (/ingest), MCP over HTTP (/mcp) and /healthz."""
    try:
        import uvicorn  # noqa: PLC0415

        from obsei.serve import create_app  # noqa: PLC0415
    except ImportError:
        raise _fail("serve needs: pip install 'obsei[mcp]'") from None
    token = os.environ.get(API_TOKEN_ENV_VAR) or None
    cfg = _load(config)
    has_access = token or cfg.access.users or cfg.access.trusted_proxy
    if not has_access and host not in ("127.0.0.1", "::1", "localhost"):
        raise _fail(f"set {API_TOKEN_ENV_VAR} or configure access before binding to {host}")
    with (
        build_context(cfg) as ctx,
        _open_store(db or cfg.store.path, cfg.store.unencrypted, egress=ctx.egress) as store,
    ):
        try:
            web = create_app(cfg, ctx, store, token=token, host=host)
        except (ConfigError, PluginError, OSError, RuntimeError) as exc:
            raise _fail(exc) from None
        scheduler = web.state.scheduler
        scheduler.start()
        for name, minutes in scheduler.scheduled().items():
            typer.echo(f"scheduled {name} every {minutes} min")
        shown = "localhost" if host in ("127.0.0.1", "::1", "0.0.0.0") else host  # noqa: S104
        typer.echo(f"studio    http://{shown}:{port}/studio/")
        try:
            uvicorn.run(web, host=host, port=port, log_level="info")
        finally:
            scheduler.stop()


def _themes_context(config: Path, db: Path | None) -> tuple[ObseiConfig, Path]:
    cfg = _load(config)
    return cfg, db or cfg.store.path


@app.command()
def themes(
    config: ConfigOption = DEFAULT_PATH,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
) -> None:
    """Embed new feedback, update stable themes and list them (k-anonymous)."""
    cfg, path = _themes_context(config, db)
    settings = cfg.themes
    with (
        build_context(cfg) as ctx,
        _open_store(path, cfg.store.unencrypted, egress=ctx.egress) as store,
    ):
        try:
            labeler = ctx.chat(settings.labeler) if settings.labeler else None
            report = update_themes(store, ctx.embedder(settings.embedder), settings, labeler)
        except (KeyError, OSError, RuntimeError) as exc:
            raise _fail(exc) from None
        typer.echo(
            f"embedded {report.embedded}, assigned {report.assigned}, new themes "
            f"{report.new_themes}, duplicates {report.duplicates}, labelled {report.labeled}"
        )
        for theme in store.theme_summaries(min_size=settings.k_anonymity):
            trend = theme.last_7_days - theme.previous_7_days
            typer.echo(f"{theme.size:>6}  {trend:+5d}  {theme.id}  {theme.label or '-'}")


def _llm_hint(cfg: ObseiConfig, name: str) -> str:
    endpoint = cfg.llms.get(name)
    if endpoint is None:
        return (
            f"hint: add an llms entry named {name!r} to obsei.yaml (or set ask_llm), "
            "e.g. a local Ollama at http://localhost:11434/v1"
        )
    if endpoint.api == "decision":
        return (
            f"hint: start the decision model server for {endpoint.address} (for llama.cpp: "
            "'llama serve -hf ggml-org/Julia-1-GGUF'), or point llms."
            f"{name} in obsei.yaml at a reachable endpoint"
        )
    return (
        f"hint: start the model server at {endpoint.base_url} (for Ollama: 'ollama serve' and "
        f"'ollama pull {endpoint.model}'), or point llms.{name} in obsei.yaml at a reachable "
        "endpoint"
    )


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Your question, in any language.")],
    config: ConfigOption = DEFAULT_PATH,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
) -> None:
    """Answer a question from your feedback with your model, citing record ids."""
    cfg, path = _themes_context(config, db)
    with (
        build_context(cfg) as ctx,
        _open_store(path, cfg.store.unencrypted, read_only=True) as store,
    ):
        try:
            answer = ask_feedback(
                store,
                question,
                ctx.chat(cfg.ask_llm),
                embedder=ctx.embedder(cfg.themes.embedder),
                k_anonymity=cfg.themes.k_anonymity,
                judge=ctx.decision(cfg.ask_judge) if cfg.ask_judge else None,
                judge_threshold=cfg.ask_judge_threshold,
            )
        except LlmUnreachableError as exc:
            raise _fail(f"{exc}\n{_llm_hint(cfg, cfg.ask_llm)}") from None
        except KeyError as exc:
            hint = "" if cfg.ask_llm in cfg.llms else f"\n{_llm_hint(cfg, cfg.ask_llm)}"
            raise _fail(f"{exc.args[0] if exc.args else exc}{hint}") from None
        except (OSError, RuntimeError) as exc:
            raise _fail(exc) from None
    typer.echo(answer.text)
    if answer.citations:
        typer.echo("\nsources: " + ", ".join(answer.citations))
    if answer.grounded is not None:
        typer.echo(f"grounded: {answer.grounded:.2f}")
    if answer.unsupported:
        typer.echo(
            "warning: the answer may not be supported by the cited feedback "
            f"(grounded {answer.grounded:.2f} < {cfg.ask_judge_threshold:g}); check the sources",
            err=True,
        )
    if answer.judge_error:
        typer.echo(f"warning: grounding check failed: {answer.judge_error}", err=True)


@app.command("studio")
def studio_export(
    out: Annotated[Path, typer.Option(help="Directory for the static Studio.")],
    config: ConfigOption = DEFAULT_PATH,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
) -> None:
    """Export a static, read-only Studio snapshot (k-anonymous) to a directory."""
    cfg, path = _themes_context(config, db)
    with _open_store(path, cfg.store.unencrypted, read_only=True) as store:
        studio.export(store, out, k=cfg.themes.k_anonymity)
    typer.echo(f"wrote {out}/index.html")


@app.command()
def demo(
    out: Annotated[Path, typer.Option(help="Directory for the static demo.")] = Path("demo"),
    embedder: Annotated[
        str,
        typer.Option(
            help="'hashing' (offline), or 'local' / 'local:<model>' to group across languages "
            "(obsei[embeddings]; run 'obsei models download' first)."
        ),
    ] = "hashing",
    decision_url_env: Annotated[
        str | None,
        typer.Option(
            help="Environment variable holding a decision endpoint URL: label the demo with that "
            "model instead of the committed labels."
        ),
    ] = None,
    decision_model: Annotated[
        str, typer.Option(help="Model name recorded with labels from --decision-url-env.")
    ] = DECISION_MODEL,
    save_labels: Annotated[
        Path | None,
        typer.Option(help="Also write the labels from --decision-url-env to this JSON file."),
    ] = None,
) -> None:
    """Build the static Studio demo from synthetic multilingual feedback."""
    if save_labels is not None and decision_url_env is None:
        raise typer.BadParameter("--save-labels needs --decision-url-env")
    settings = ThemesConfig(embedder=embedder, k_anonymity=5)
    llms = (
        {"demo": LlmEndpoint(api="decision", url_env=decision_url_env, timeout=120)}
        if decision_url_env
        else {}
    )
    with (
        Context(egress=EgressPolicy.from_env(), llms=llms) as ctx,
        Store(allow_unencrypted=True) as store,
    ):
        try:
            model = ctx.embedder(settings.embedder)
            raw = raw_demo_records()
            labels = None
            if decision_url_env:
                labels = decision_labels(
                    redacted_demo_records(raw), ctx.decision("demo"), model=decision_model
                )
                if save_labels is not None:
                    write_labels(labels, save_labels)
            store.upsert(demo_records(raw, labels))
            update_themes(store, model, settings)
        except (KeyError, OSError, RuntimeError, LlmError) as exc:
            raise _fail(exc) from None
        snap = demo_snapshot(store, raw, k=settings.k_anonymity, embedder=model.model)
        studio.write(out, snap)
    typer.echo(f"wrote {out}/index.html; serve it with: python -m http.server -d {out}")


models_app = typer.Typer(help="Download local models for offline (air-gapped) use.")
app.add_typer(models_app, name="models")


@models_app.command("download")
def models_download(
    embeddings: Annotated[str, typer.Option(help="Embedding model for themes.")] = LOCAL_MODEL,
    directory: Annotated[
        Path | None, typer.Option("--dir", envvar=MODELS_DIR_ENV, help="Model cache directory.")
    ] = None,
) -> None:
    """Fetch the multilingual embedding model so 'themes.embedder: local' works offline."""
    try:
        LocalEmbedder(embeddings, cache_dir=str(directory) if directory else None, offline=False)
    except LlmError as exc:
        raise _fail(exc) from None
    where = directory or os.environ.get(MODELS_DIR_ENV) or "the fastembed cache"
    typer.echo(f"downloaded {embeddings} to {where}; set {MODELS_DIR_ENV} to use it offline")
