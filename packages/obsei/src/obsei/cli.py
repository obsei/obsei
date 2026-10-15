from __future__ import annotations

import getpass
import json
import os
import platform
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from importlib.util import find_spec
from itertools import islice
from pathlib import Path
from typing import Annotated

import duckdb
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
from rich.text import Text

from obsei import __version__, studio
from obsei.alerts import Fired, check_alerts
from obsei.ask import ask as ask_feedback
from obsei.config import (
    DEFAULT_PATH,
    SECRETS_PATH,
    ConfigError,
    ObseiConfig,
    PipelineConfig,
    PluginSpec,
    StoreConfig,
    build_context,
    build_pipeline,
    builtin_registry,
    load_config,
    load_secrets,
    write_secrets,
)
from obsei.core.context import Context, LlmEndpoint
from obsei.core.protocols import Drops, Enricher, ReportsErrors
from obsei.core.record import Record
from obsei.core.registry import PluginError
from obsei.demo import (
    DECISION_MODEL,
    GOLD_CONFIG,
    GOLD_FILE,
    decision_labels,
    demo_records,
    demo_snapshot,
    raw_demo_records,
    redacted_demo_records,
    write_labels,
)
from obsei.enrichers.classify import ClassifyPluginConfig, build_classifier
from obsei.evaluate import (
    CLASSIFY,
    EvalReport,
    correct,
    corrected_examples,
    corrections,
    evaluate,
    gold_examples,
    path,
    questions,
    read_labels,
)
from obsei.llm import EgressPolicy
from obsei.llm.client import LlmError, LlmUnreachableError
from obsei.llm.embed import LOCAL_MODEL, MODELS_DIR_ENV, LocalEmbedder
from obsei.llm.local import LOCAL_CLASSIFIER, fetch
from obsei.pipeline import Pipeline
from obsei.preview import PreviewError, Redaction, labels, redactions, resolve
from obsei.privacy.names import redactor_for
from obsei.privacy.pseudonym import SALT_ENV_VAR, PseudonymSaltError, load_salt, pseudonymize
from obsei.privacy.redact import RegexRedactor
from obsei.routing import answer
from obsei.runner import RUN_ERRORS, run_pipelines
from obsei.store import (
    DB_KEY_ENV_VAR,
    EXTENSIONS_ENV_VAR,
    INSTALL_HINT,
    PREINSTALL_HINT,
    AlertState,
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


ConfigOption = Annotated[
    Path, typer.Option("--config", "-c", envvar="OBSEI_CONFIG", help="Path to obsei.yaml.")
]


@app.command()
def version() -> None:
    """Show the obsei version."""
    typer.echo(f"obsei {__version__}")


@app.command()
def doctor(config: ConfigOption = DEFAULT_PATH) -> None:
    """Check the local environment and list discovered plugins."""
    loaded = load_secrets(config)

    def origin(name: str) -> str:
        return f"from {config.parent / SECRETS_PATH}" if name in loaded else "from the environment"

    typer.echo(f"obsei     {__version__}")
    typer.echo(f"python    {platform.python_version()} ({sys.platform})")
    try:
        load_salt()
        salt_status = f"configured ({origin(SALT_ENV_VAR)})"
    except PseudonymSaltError:
        salt_status = "not set (OBSEI_PSEUDONYM_SALT is required before ingesting authors)"
    typer.echo(f"salt      {salt_status}")
    try:
        key_status = (
            f"configured ({origin(DB_KEY_ENV_VAR)})"
            if load_db_key()
            else f"not set ({DB_KEY_ENV_VAR})"
        )
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
API_TOKEN_ENV_VAR = "OBSEI_API_TOKEN"  # noqa: S105

UnencryptedOption = Annotated[
    bool,
    typer.Option("--unencrypted", help="Open without an encryption key (encrypted disks only)."),
]


def _fail(message: object) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(2)


def _load(config: Path) -> ObseiConfig:
    load_secrets(config)
    try:
        return load_config(config)
    except ConfigError as exc:
        raise _fail(exc) from None


def _context(cfg: ObseiConfig) -> Context:
    try:
        return build_context(cfg)
    except PseudonymSaltError as exc:
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
    load_secrets(config)
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
    settings = _store_settings(config, db, unencrypted)
    pseudonym = _author_pseudonym(author)
    with _open_existing(settings) as store:
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


CLASSIFY_OFF = "    # enrichers:\n    #   - type: classify\n    #     config:"
CLASSIFY_ON = "    enrichers:\n      - type: classify\n        config:"
LOCAL_HINT = (
    "to label feedback on this machine: pip install 'obsei[local]', run 'obsei models download' "
    "and uncomment the classify enricher in obsei.yaml"
)
MODEL_HINT = (
    "hint: for the local classifier, pip install 'obsei[local]' and run 'obsei models download'; "
    "for a model server, start it or point llms in obsei.yaml at a reachable endpoint"
)


@app.command()
def init(
    directory: Annotated[Path, typer.Argument(help="Where to create the project.")] = Path(),
    force: Annotated[bool, typer.Option(help="Overwrite obsei.yaml and feedback.csv.")] = False,
    offline: Annotated[
        bool,
        typer.Option(help="Skip downloading DuckDB's httpfs extension and the classifier model."),
    ] = False,
) -> None:
    """Create obsei.yaml, a sample dataset and local secrets; install DuckDB's encryption
    extension and, with obsei[local], the classifier model.

    Secrets go to .obsei/secrets.env (owner-only, git-ignored) and are never overwritten."""
    templates = resources.files("obsei") / "templates"
    local = find_spec("gliner2") is not None
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("obsei.yaml", "feedback.csv"):
        target = directory / name
        if target.exists() and not force:
            typer.echo(f"skip   {target} (exists)")
            continue
        text = (templates / name).read_text(encoding="utf-8")
        target.write_text(text.replace(CLASSIFY_OFF, CLASSIFY_ON) if local else text, "utf-8")
        typer.echo(f"create {target}")
    created = write_secrets(directory)
    if created is None:
        typer.echo(f"skip   {directory / SECRETS_PATH} (exists)")
    else:
        typer.echo(f"create {created} (database key and pseudonym salt: back it up)")
    _ignore_secrets(directory / ".gitignore")
    if not offline:
        _install_encryption()
        if local:
            _download_classifier()
    if not local:
        typer.echo(f"hint   {LOCAL_HINT}")
    typer.echo("next   obsei try  (redacted, labelled preview; nothing stored), then obsei run")


def _ignore_secrets(gitignore: Path) -> None:
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if {".obsei", ".obsei/"} & {line.strip() for line in text.splitlines()}:
        return
    separator = "\n" if text and not text.endswith("\n") else ""
    gitignore.write_text(f"{text}{separator}.obsei/\n", encoding="utf-8")
    typer.echo(f"ignore .obsei/ in {gitignore}")


def _download_classifier() -> None:
    typer.echo(f"download {LOCAL_CLASSIFIER} (once, about 2.2 GB; it runs on this machine)")
    try:
        fetch(LOCAL_CLASSIFIER, offline=False)
    except LlmError as exc:
        typer.echo(f"warn   {exc}; run 'obsei models download' later", err=True)


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
        _context(cfg) as ctx,
        _open_store(db or cfg.store.path, cfg.store.unencrypted, egress=ctx.egress) as store,
    ):
        outcomes = run_pipelines(cfg, ctx, store, names)
        for outcome in outcomes:
            typer.echo(outcome.summary(), err=not outcome.ok)
            for warning in outcome.warnings():
                typer.echo(f"warning: {warning}", err=True)
        failures = {o.pipeline: o.error for o in outcomes if o.error}
        alerted = _alert(lambda: check_alerts(cfg, ctx, store, failures=failures))
    return not all(o.ok for o in outcomes) or not alerted


TARGET_HELP = (
    "An App Store, GitHub repo, Hacker News or RSS/Atom link, or a .csv, .jsonl or .json file "
    "(default: the sources in obsei.yaml)."
)
PREVIEW_FIELDS = {"source", "text", "created_at", "rating", "lang", "context", "enrichments"}
PREVIEW_CHARS = 160


def _without_enrichers(cfg: ObseiConfig) -> ObseiConfig:
    pipelines = [p.model_copy(update={"enrichers": []}) for p in cfg.pipelines]
    return cfg.model_copy(update={"pipelines": pipelines})


def _preview_config(config: Path, target: str, pipeline: list[str] | None) -> ObseiConfig:
    """One pipeline reading ``target``, with redaction on and the configured enrichers (else the
    local classifier when obsei[local] is installed)."""
    try:
        entry = resolve(target)
    except PreviewError as exc:
        raise _fail(exc) from None
    if config.exists() or config != DEFAULT_PATH:
        cfg = _load(config)
        try:
            source = cfg.pipeline(pipeline[0]) if pipeline else cfg.pipelines[0]
        except ConfigError as exc:
            raise _fail(exc) from None
        privacy = cfg.privacy.model_copy(update={"redact": True})
        preview = PipelineConfig(name="try", sources=[entry], enrichers=source.enrichers)
        return cfg.model_copy(update={"privacy": privacy, "pipelines": [preview]})
    load_secrets(config)
    local = find_spec("gliner2") is not None
    classify = PluginSpec(type="classify", config={"llm": "default", "threshold": 0.4})
    return ObseiConfig(
        llms={"default": LlmEndpoint(api="local")} if local else {},
        pipelines=[
            PipelineConfig(name="try", sources=[entry], enrichers=[classify] if local else [])
        ],
    )


def _preview_pipeline(cfg: ObseiConfig, name: str, ctx: Context) -> Pipeline:
    """Without a usable model the preview still shows redaction, with a warning."""
    try:
        return build_pipeline(cfg, name, ctx, with_sinks=False)
    except LlmError as exc:
        typer.echo(f"warning: no labels: {exc}\n{MODEL_HINT}", err=True)
        return _preview_pipeline(_without_enrichers(cfg), name, ctx)
    except (ConfigError, PluginError, OSError, RuntimeError, ValueError) as exc:
        raise _fail(exc) from None


def _enrich_preview(built: Pipeline, where: str, records: list[Record]) -> list[Record]:
    for enricher in built.enrichers:
        results = enricher.enrich(records)
        records = [
            r if e is None else r.with_enrichment(enricher.name, e)
            for r, e in zip(records, results, strict=True)
        ]
        missing = sum(e is None for e in results)
        if missing:
            reason = enricher.last_error if isinstance(enricher, ReportsErrors) else None
            typer.echo(
                f"warning: {where}: {enricher.name} gave no answer for {missing} record(s)"
                f"{f': {reason}' if reason else ''}\n{MODEL_HINT}",
                err=True,
            )
        if isinstance(enricher, Drops):
            kept = [r for r in records if enricher.keep(r)]
            if len(kept) < len(records):
                typer.echo(
                    f"{where}: {enricher.name} dropped {len(records) - len(kept)} record(s)",
                    err=True,
                )
            records = kept
    return records


def _line(text: str, width: int = PREVIEW_CHARS) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else f"{flat[: width - 1]}…"


def _print_preview(rows: list[tuple[str, Record]], found: list[Redaction], hint: bool) -> None:
    console = Console(highlight=False)
    if not rows:
        console.print("no records")
        return
    table = Table("source", "lang", "labels", "text", show_lines=True)
    for key, record in rows:
        table.add_row(
            Text(key),
            Text(record.lang or "-"),
            Text(labels(record) or "-"),
            Text(_line(record.text)),
        )
    console.print(table)
    if found:
        counts = sum((r.counts for r in found), Counter[str]())
        summary = ", ".join(f"{label} {n}" for label, n in sorted(counts.items()))
        console.print(
            Text(f"redacted {counts.total()} value(s) in {len(found)} record(s): {summary}")
        )
        for redaction in found[:3]:
            console.print(Text(f"  before  {_line(redaction.before, 100)}"))
            console.print(Text(f"  after   {_line(redaction.after, 100)}"))
    console.print("nothing was stored or sent; the original text exists only in this preview")
    if hint:
        console.print(Text(f"hint: {LOCAL_HINT}"))


@app.command("try")
def try_(
    target: Annotated[str | None, typer.Argument(help=TARGET_HELP, show_default=False)] = None,
    config: ConfigOption = DEFAULT_PATH,
    pipeline: PipelineOption = None,
    limit: Annotated[int, typer.Option(min=1, help="Records per source.")] = 10,
    enrich: Annotated[bool, typer.Option(help="Run the configured enrichers (classify).")] = True,
    as_json: Annotated[bool, typer.Option("--json", help="One JSON object per record.")] = False,
) -> None:
    """Preview feedback with PII redacted and labels, from your sources or a link or file.

    Nothing is stored or sent: records are fetched, redacted and labelled in memory."""
    cfg = _preview_config(config, target, pipeline) if target else _load(config)
    names = ["try"] if target else pipeline or [p.name for p in cfg.pipelines]
    if not enrich:
        cfg = _without_enrichers(cfg)
    rows: list[tuple[str, Record]] = []
    found: list[Redaction] = []
    with _context(cfg) as ctx:
        for name in names:
            built = _preview_pipeline(cfg, name, ctx)
            for spec in built.sources:
                try:
                    raw = [r for r, _ in islice(spec.source.fetch(None), limit)]
                except SyntaxError as exc:
                    raise _fail(
                        f"{target or spec.key} is not an RSS or Atom feed ({exc}); obsei try "
                        "reads App Store, GitHub, Hacker News and feed links"
                    ) from None
                except RUN_ERRORS as exc:
                    raise _fail(f"{name}/{spec.key}: {exc}") from None
                records = raw
                if built.redactor is not None:
                    records = list(built.redactor.redact(raw))
                    found += redactions(spec.key, raw, records)
                records = _enrich_preview(built, f"{name}/{spec.key}", records)
                if as_json:
                    for record in records:
                        typer.echo(record.model_dump_json(include=PREVIEW_FIELDS))
                rows += [(spec.key, r) for r in records]
    if not as_json:
        labelled = any("classify" in r.enrichments for _, r in rows)
        _print_preview(rows, found, hint=enrich and not labelled)


@app.command()
def mcp(
    config: ConfigOption = DEFAULT_PATH,
    db: Annotated[Path | None, typer.Option("--db", envvar="OBSEI_DB")] = None,
) -> None:
    """Serve read-only MCP tools over stdio (Claude, ChatGPT, Cursor, your agents)."""
    from obsei.mcp_server import create_server  # noqa: PLC0415

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
    import uvicorn  # noqa: PLC0415

    from obsei.serve import create_app  # noqa: PLC0415

    token = os.environ.get(API_TOKEN_ENV_VAR) or None
    cfg = _load(config)
    has_access = token or cfg.access.users or cfg.access.trusted_proxy
    if not has_access and host not in ("127.0.0.1", "::1", "localhost"):
        raise _fail(f"set {API_TOKEN_ENV_VAR} or configure access before binding to {host}")
    with (
        _context(cfg) as ctx,
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
        _context(cfg) as ctx,
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
            rising = "  rising" if theme.rising else ""
            typer.echo(f"{theme.size:>6}  {trend:+5d}  {theme.id}  {theme.label or '-'}{rising}")
        if not _alert(lambda: check_alerts(cfg, ctx, store)):
            raise typer.Exit(1)


def _llm_hint(cfg: ObseiConfig, name: str) -> str:
    endpoint = cfg.llms.get(name)
    if endpoint is None or endpoint.api != "openai":
        return (
            "hint: ask needs a chat model: add one under llms in obsei.yaml and set ask_llm to "
            "its name, e.g. a local Ollama at http://localhost:11434/v1"
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
        _context(cfg) as ctx,
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
            chat = cfg.llms.get(cfg.ask_llm)
            hint = "" if chat and chat.api == "openai" else f"\n{_llm_hint(cfg, cfg.ask_llm)}"
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


ClassifyPipelineOption = Annotated[
    str | None,
    typer.Option(
        "--pipeline", "-p", help="Pipeline whose classify enricher to use (default: the first)."
    ),
]


def _classify_config(cfg: ObseiConfig, pipeline: str | None) -> ClassifyPluginConfig:
    try:
        candidates = [cfg.pipeline(pipeline)] if pipeline else cfg.pipelines
        spec = next((e for p in candidates for e in p.enrichers if e.type == CLASSIFY), None)
        if spec is None:
            raise _fail(f"no classify enricher in {pipeline or 'any pipeline'}")
        return ClassifyPluginConfig.model_validate(spec.config)
    except (ConfigError, ValidationError) as exc:
        raise _fail(exc) from None


def _classifier(config: ClassifyPluginConfig, ctx: Context) -> Enricher:
    try:
        return build_classifier(config, ctx)
    except (KeyError, ValueError, OSError, RuntimeError, LlmError) as exc:
        raise _fail(exc) from None


@app.command("eval")
def eval_(
    gold: Annotated[
        Path | None,
        typer.Argument(
            help="CSV with text, optional lang and a column per question: sentiment, intent or "
            "a field name."
        ),
    ] = None,
    config: ConfigOption = DEFAULT_PATH,
    pipeline: ClassifyPipelineOption = None,
    demo: Annotated[
        bool, typer.Option("--demo", help="The demo gold set with the local default classifier.")
    ] = False,
    from_store: Annotated[
        bool, typer.Option("--from-store", help="Use the human-corrected records as gold.")
    ] = False,
    db: DbOption = None,
    target_precision: Annotated[
        float, typer.Option(min=0.0, max=1.0, help="Accuracy the suggested cutoffs keep.")
    ] = 0.9,
    min_accuracy: Annotated[
        float | None,
        typer.Option(min=0.0, max=1.0, help="Exit 1 when a question's accuracy is lower."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the report as JSON.")] = False,
) -> None:
    """Measure the classifier on labelled feedback and suggest a cutoff per question."""
    if (gold is not None) + demo + from_store != 1:
        raise _fail("pass a gold CSV, --demo or --from-store")
    if demo:
        classify = GOLD_CONFIG
        ctx = Context(egress=EgressPolicy.from_env(), llms={"default": LlmEndpoint(api="local")})
        with resources.as_file(resources.files("obsei") / "templates" / GOLD_FILE) as file:
            examples = gold_examples(file, questions(classify), RegexRedactor())
    else:
        cfg = _load(config)
        classify = _classify_config(cfg, pipeline)
        ctx = build_context(cfg)
        if gold is None:
            path = db or cfg.store.path
            with _open_store(
                path, cfg.store.unencrypted, read_only=True, egress=ctx.egress, must_exist=True
            ) as store:
                examples = corrected_examples(store.iter_records())
            if not examples:
                raise _fail(f"no corrected records in {path}; add labels with 'obsei correct'")
        else:
            redactor = (
                redactor_for(cfg.privacy.regions, cfg.privacy.names, ctx.egress)
                if cfg.privacy.redact
                else None
            )
            try:
                examples = gold_examples(gold, questions(classify), redactor)
            except (OSError, ValueError) as exc:
                raise _fail(exc) from None
    with ctx:
        classifier = _classifier(classify, ctx)
        report = evaluate(classifier, examples, classify, target_precision=target_precision)
    if report.records and report.failed == report.records:
        reason = classifier.last_error if isinstance(classifier, ReportsErrors) else None
        raise _fail(f"the classifier labelled no record: {reason or 'no answer'}")
    if as_json:
        typer.echo(report.model_dump_json(indent=2))
    else:
        _print_report(report)
    if min_accuracy is not None and any(q.accuracy < min_accuracy for q in report.questions):
        raise typer.Exit(1)


def _print_report(report: EvalReport) -> None:
    failed = f", {report.failed} not labelled" if report.failed else ""
    typer.echo(
        f"{report.records} records, model {report.model or '-'}, "
        f"{report.review_rate:.0%} marked for review{failed}\n"
    )
    typer.echo(
        f"{'question':<12}{'n':>5}{'accuracy':>10}{'macro F1':>10}{'ECE':>6}{'Brier':>7}"
        f"{'cutoff':>8}{'review':>8}{'kept':>6}{'suggest':>9}{'review':>8}  worst language"
    )
    for q in report.questions:
        s, worst = q.suggested, q.worst_language
        typer.echo(
            f"{q.question:<12}{q.n:>5}{q.accuracy:>10.2f}{q.macro_f1:>10.2f}{q.ece:>6.2f}"
            f"{q.brier:>7.2f}{q.current.cutoff:>8.2f}{q.current.review_rate:>8.0%}"
            f"{q.current.accuracy:>6.2f}"
            + (f"{s.cutoff:>9.2f}{s.review_rate:>8.0%}" if s else f"{'-':>9}{'-':>8}")
            + (f"  {worst.lang} {worst.accuracy:.2f}" if worst else "  -")
        )
    typer.echo("\nmost common mistakes (expected -> answered):")
    for q in report.questions:
        mistakes = ", ".join(f"{c.gold} -> {c.predicted or '-'} ({c.count})" for c in q.confusions)
        typer.echo(f"{q.question:<12}{mistakes or 'none'}")
    typer.echo(
        f"\nkept: accuracy of answers at or above the cutoff; suggest: the lowest cutoff whose "
        f"kept answers are {report.target_precision:.0%} right (set it under min_confidence)"
    )


REPROCESS_BATCH = 100


@app.command()
def reprocess(
    config: ConfigOption = DEFAULT_PATH,
    pipeline: ClassifyPipelineOption = None,
    db: DbOption = None,
    since: Annotated[
        datetime | None, typer.Option(help="Only records created on or after this date (UTC).")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report the changes without writing them.")
    ] = False,
) -> None:
    """Relabel stored records with the current classify config; human corrections are kept."""
    cfg = _load(config)
    classify = _classify_config(cfg, pipeline)
    options = questions(classify)
    changes: Counter[tuple[str, str | None, str | None]] = Counter()
    relabelled = 0
    with (
        build_context(cfg) as ctx,
        _open_store(
            db or cfg.store.path,
            cfg.store.unencrypted,
            read_only=dry_run,
            egress=ctx.egress,
            must_exist=True,
        ) as store,
    ):
        classifier = _classifier(classify, ctx)
        start = since.replace(tzinfo=UTC) if since else None
        records = [r for r in store.iter_records(since=start) if CLASSIFY in r.enrichments]
        for first in range(0, len(records), REPROCESS_BATCH):
            batch = records[first : first + REPROCESS_BATCH]
            updated = []
            for record, result in zip(batch, classifier.enrich(batch), strict=True):
                if result is None:
                    continue
                kept = corrections(record)
                new = record.with_enrichment(CLASSIFY, correct(result, kept) if kept else result)
                for q in options:
                    before, after = answer(record, path(q))[0], answer(new, path(q))[0]
                    if before != after:
                        changes[q, before, after] += 1
                updated.append(new)
            relabelled += len(updated)
            if not dry_run:
                store.upsert(updated)
        if not dry_run:
            store.audit(
                "reprocess",
                {"pipeline": pipeline, "records": relabelled, "changed": sum(changes.values())},
            )
    failed = len(records) - relabelled
    typer.echo(
        f"relabelled {relabelled} record(s)"
        + (f", {failed} not labelled" if failed else "")
        + (" (dry run: nothing written)" if dry_run else "")
    )
    for q in options:
        moves = [(k, n) for k, n in changes.most_common() if k[0] == q]
        top = ", ".join(f"{a or '-'} -> {b or '-'} ({n})" for (_, a, b), n in moves[:3])
        typer.echo(f"{q:<12}{sum(n for _, n in moves):>5} changed" + (f": {top}" if top else ""))


@app.command("correct")
def correct_(
    file: Annotated[
        Path, typer.Argument(help="CSV with id (the record id) and a column per question.")
    ],
    config: ConfigOption = DEFAULT_PATH,
    pipeline: ClassifyPipelineOption = None,
    db: DbOption = None,
) -> None:
    """Store human labels: they replace the model's answers and are kept by reprocess."""
    cfg = _load(config)
    try:
        rows = read_labels(file, questions(_classify_config(cfg, pipeline)), "id")
    except (OSError, ValueError) as exc:
        raise _fail(exc) from None
    updated, missing = [], []
    with _open_store(
        db or cfg.store.path, cfg.store.unencrypted, egress=cfg.egress, must_exist=True
    ) as store:
        for row, labels in rows:
            record = store.get(row["id"])
            if record is None:
                missing.append(row["id"])
            elif labels:
                fixed = correct(record.enrichments.get(CLASSIFY), labels)
                updated.append(record.with_enrichment(CLASSIFY, fixed))
        store.upsert(updated)
        store.audit("correct", {"records": len(updated)})
    typer.echo(f"corrected {len(updated)} record(s)")
    if missing:
        typer.echo(f"warning: no record with id {', '.join(missing)}", err=True)


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


alerts_app = typer.Typer(help="Theme spikes, new themes, digests, review queue and health alerts.")
app.add_typer(alerts_app, name="alerts")
AlertArgument = Annotated[str, typer.Argument(help="Alert name in obsei.yaml.")]
KeyArgument = Annotated[str, typer.Argument(help="Theme id, digest, review, or a pipeline.")]


def _alert(check: Callable[[], list[Fired]], *, dry_run: bool = False) -> bool:
    """Print what fired; False when an alert could not be delivered or built."""
    try:
        fired = check()
    except (ConfigError, PluginError, OSError, RuntimeError, ValueError) as exc:
        typer.echo(f"error: alerts: {exc}", err=True)
        return False
    for item in fired:
        prefix = "would fire" if dry_run else "alert"
        typer.echo(f"{prefix} {item.alert.alert} {item.alert.key}: {item.alert.title}")
        for line in item.alert.lines if dry_run else ():
            typer.echo(f"  {line}")
        for error in item.errors:
            typer.echo(f"error: alert {item.alert.alert}: {error}", err=True)
    return not any(item.errors for item in fired)


def _alert_state(cfg: ObseiConfig, store: Store, alert: str, key: str) -> AlertState:
    if alert not in {a.name for a in cfg.alerts}:
        raise _fail(f"no alert named {alert!r}")
    found = [s for s in store.alert_states() if (s.alert, s.key) == (alert, key)]
    return found[0] if found else AlertState(alert=alert, key=key)


@alerts_app.command("check")
def alerts_check(
    config: ConfigOption = DEFAULT_PATH,
    db: DbOption = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print what would fire; send and record nothing.")
    ] = False,
) -> None:
    """Evaluate every alert now and deliver those due."""
    cfg, path = _themes_context(config, db)
    with (
        build_context(cfg) as ctx,
        _open_store(path, cfg.store.unencrypted, egress=ctx.egress) as store,
    ):
        ok = _alert(lambda: check_alerts(cfg, ctx, store, dry_run=dry_run), dry_run=dry_run)
    if not ok:
        raise typer.Exit(1)


@alerts_app.command("list")
def alerts_list(config: ConfigOption = DEFAULT_PATH, db: DbOption = None) -> None:
    """Show when each alert last fired, and snoozes and acks."""
    cfg, path = _themes_context(config, db)
    with _open_store(path, cfg.store.unencrypted, read_only=True, must_exist=True) as store:
        states = store.alert_states()
    for name in [a.name for a in cfg.alerts if not any(s.alert == a.name for s in states)]:
        typer.echo(f"{name}  -  never fired")
    for s in states:
        parts = [f"fired {s.last_fired_at:%Y-%m-%d %H:%M}" if s.last_fired_at else "not fired"]
        if s.snoozed_until:
            parts.append(f"snoozed until {s.snoozed_until:%Y-%m-%d %H:%M}")
        if s.acked_at:
            parts.append(f"acked by {s.acked_by} {s.acked_at:%Y-%m-%d %H:%M}")
        typer.echo(f"{s.alert}  {s.key}  {', '.join(parts)} UTC")


@alerts_app.command("snooze")
def alerts_snooze(
    alert: AlertArgument,
    key: KeyArgument,
    hours: Annotated[int, typer.Option(min=1, help="Snooze for this many hours.")] = 24,
    config: ConfigOption = DEFAULT_PATH,
    db: DbOption = None,
) -> None:
    """Silence one alert key for a while."""
    cfg, path = _themes_context(config, db)
    until = datetime.now(UTC) + timedelta(hours=hours)
    with _open_store(path, cfg.store.unencrypted, must_exist=True) as store:
        state = _alert_state(cfg, store, alert, key)
        store.put_alert_state(state.model_copy(update={"snoozed_until": until}))
    typer.echo(f"snoozed {alert} {key} until {until:%Y-%m-%d %H:%M} UTC")


@alerts_app.command("ack")
def alerts_ack(
    alert: AlertArgument,
    key: KeyArgument,
    by: Annotated[str | None, typer.Option(help="Who acknowledges (default: your user).")] = None,
    config: ConfigOption = DEFAULT_PATH,
    db: DbOption = None,
) -> None:
    """Acknowledge one alert key: it does not fire again for 7 days."""
    cfg, path = _themes_context(config, db)
    with _open_store(path, cfg.store.unencrypted, must_exist=True) as store:
        state = _alert_state(cfg, store, alert, key)
        update = {"acked_by": by or getpass.getuser(), "acked_at": datetime.now(UTC)}
        store.put_alert_state(state.model_copy(update=update))
    typer.echo(f"acknowledged {alert} {key}")


models_app = typer.Typer(help="Download local models for offline (air-gapped) use.")
app.add_typer(models_app, name="models")


@models_app.command("download")
def models_download(
    embeddings: Annotated[
        str | None,
        typer.Option(
            help=f"Embedding model for themes [default: {LOCAL_MODEL} with obsei[embeddings]]."
        ),
    ] = None,
    classifier: Annotated[
        list[str] | None,
        typer.Option(
            help=f"Model for 'api: local', repeatable "
            f"[default: {LOCAL_CLASSIFIER} with obsei[local]]."
        ),
    ] = None,
    directory: Annotated[
        Path | None, typer.Option("--dir", envvar=MODELS_DIR_ENV, help="Model cache directory.")
    ] = None,
) -> None:
    """Fetch the local embedding and classifier models so they work offline (air-gapped)."""
    if embeddings is None and find_spec("fastembed"):
        embeddings = LOCAL_MODEL
    if classifier is None:
        classifier = [LOCAL_CLASSIFIER] if find_spec("gliner2") else []
    if not embeddings and not classifier:
        raise _fail("nothing to download: pip install 'obsei[local]' or 'obsei[embeddings]' first")
    cache = str(directory) if directory else None
    try:
        if embeddings:
            LocalEmbedder(embeddings, cache_dir=cache, offline=False)
            typer.echo(f"downloaded {embeddings}")
        for model in classifier:
            fetch(model, offline=False, cache_dir=cache)
            typer.echo(f"downloaded {model}")
    except LlmError as exc:
        raise _fail(exc) from None
    where = cache or os.environ.get(MODELS_DIR_ENV) or "the default cache"
    typer.echo(f"models are in {where}; set {MODELS_DIR_ENV} to use them offline")
