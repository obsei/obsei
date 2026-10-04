"""The ``obsei`` command line."""

from __future__ import annotations

import json
import platform
import sys
from typing import Annotated

import typer

from obsei import __version__
from obsei.core.record import Record
from obsei.core.registry import PLUGIN_KINDS, Registry
from obsei.privacy.pseudonym import PseudonymSaltError, load_salt

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
    """obsei command line."""


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
    registry = Registry()
    loaded = registry.load_entry_points()
    typer.echo(f"plugins   {', '.join(loaded) if loaded else 'none installed'}")
    for kind in PLUGIN_KINDS:
        names = registry.names(kind)
        if names:
            typer.echo(f"  {kind:<9}{', '.join(names)}")


@app.command()
def schema() -> None:
    """Print the Feedback Record JSON Schema."""
    typer.echo(json.dumps(Record.model_json_schema(), indent=2, sort_keys=True))
