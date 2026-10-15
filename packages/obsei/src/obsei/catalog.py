"""Every source, enricher and sink obsei can use, built in or from an installed plugin, and the
JSON Schema of ``obsei.yaml`` with each plugin's ``config``."""

from __future__ import annotations

from importlib.metadata import entry_points

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue, models_json_schema

from obsei.config import ObseiConfig, builtin_registry
from obsei.core.plugin import SECRET
from obsei.core.registry import ENTRY_POINT_GROUP, PluginKind, Registry

SCHEMA_URL = "https://docs.obsei.com/schema/obsei.schema.json"
ENTRIES: dict[str, PluginKind] = {
    "SourceEntry": "source",
    "PluginSpec": "enricher",
    "SinkEntry": "sink",
}


class Integration(BaseModel):
    kind: PluginKind
    name: str
    title: str
    category: str
    status: str
    docs_url: str | None
    help_url: str | None
    secrets: list[str]
    plugin: str | None = None


def secret_fields(model: type[BaseModel]) -> list[str]:
    return [n for n, f in model.model_fields.items() if f.json_schema_extra == SECRET]


def installed() -> tuple[Registry, dict[tuple[PluginKind, str], str]]:
    """The built-ins plus every installed plugin, with the entry point that adds each plugin."""
    registry = builtin_registry()
    owners: dict[tuple[PluginKind, str], str] = {}
    for ep in sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name):
        before = {(kind, name) for kind, name, _ in registry.plugins()}
        registry.load_entry_points(allow=[ep.name])
        for kind, name, _ in registry.plugins():
            if (kind, name) not in before:
                owners[kind, name] = ep.name
    return registry, owners


def integrations(
    registry: Registry, owners: dict[tuple[PluginKind, str], str]
) -> list[Integration]:
    found = []
    for kind, name, plugin in registry.plugins():
        catalog = plugin.catalog
        model = plugin.config_model
        found.append(
            Integration(
                kind=kind,
                name=name,
                title=catalog.title if catalog else name,
                category=catalog.category if catalog else "other",
                status=catalog.status if catalog else "unknown",
                docs_url=catalog.docs_url if catalog else None,
                help_url=catalog.help_url if catalog else None,
                secrets=[
                    default if isinstance(default := model.model_fields[f].default, str) else f
                    for f in secret_fields(model)
                ],
                plugin=owners.get((kind, name)),
            )
        )
    return found


def config_schema(registry: Registry) -> JsonSchemaValue:
    """``obsei.yaml``'s schema; each entry's ``config`` follows its ``type``'s model."""
    plugins = list(registry.plugins())
    models: list[type[BaseModel]] = list(
        dict.fromkeys([ObseiConfig, *(p.config_model for _, _, p in plugins)])
    )
    refs, schema = models_json_schema([(m, "validation") for m in models])
    defs = schema["$defs"]
    top = defs.pop("ObseiConfig")
    for entry, kind in ENTRIES.items():
        spec = defs[entry]
        typed = [(n, p.config_model) for k, n, p in plugins if k == kind]
        spec["properties"]["type"] = {
            "anyOf": [{"enum": [n for n, _ in typed]}, {"type": "string"}],
            "description": f"The {kind}: run 'obsei integrations' to list them.",
        }
        spec["allOf"] = [
            {
                "if": {"properties": {"type": {"const": name}}, "required": ["type"]},
                "then": {"properties": {"config": refs[model, "validation"]}},
            }
            for name, model in typed
        ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_URL,
        **top,
        "$defs": defs,
    }
