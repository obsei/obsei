"""Typed plugin factories: a pydantic config model plus a ``build(config, ctx)`` callable."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context

C = TypeVar("C", bound=BaseModel)
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

Category: TypeAlias = Literal[
    "reviews", "support", "social", "surveys", "data", "chat", "issues", "warehouse", "notify"
]
SECRET: dict[str, JsonValue] = {"secret": True}
"""``json_schema_extra`` of a field that names the environment variable holding a secret."""


class Catalog(BaseModel):
    """How ``obsei integrations`` and ``obsei add`` present a plugin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    category: Category | Literal["enrich"]
    status: Literal["verified", "beta"] = "beta"
    docs_url: str
    help_url: str | None = Field(
        default=None, description="The provider's page on getting the credential, if one is needed."
    )
    ask: tuple[str, ...] = Field(
        default=(), description="Optional fields obsei add asks for, besides required and secrets."
    )


class Factory(Protocol[T_co]):
    @property
    def config_model(self) -> type[BaseModel]: ...

    @property
    def catalog(self) -> Catalog | None: ...

    def create(self, config: Mapping[str, JsonValue], ctx: Context) -> T_co: ...


@dataclass(frozen=True)
class PluginFactory(Generic[C, T]):
    config: type[C]
    build: Callable[[C, Context], T]
    catalog: Catalog | None = None

    @property
    def config_model(self) -> type[BaseModel]:
        return self.config

    def create(self, config: Mapping[str, JsonValue], ctx: Context) -> T:
        return self.build(self.config.model_validate(config), ctx)


def factory(
    config: type[C], build: Callable[[C, Context], T], catalog: Catalog | None = None
) -> PluginFactory[C, T]:
    return PluginFactory(config, build, catalog)
