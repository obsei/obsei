"""Typed plugin factories: a pydantic config model plus a ``build(config, ctx)`` callable."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, JsonValue

from obsei.core.context import Context

C = TypeVar("C", bound=BaseModel)
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Factory(Protocol[T_co]):
    @property
    def config_model(self) -> type[BaseModel]: ...

    def create(self, config: Mapping[str, JsonValue], ctx: Context) -> T_co: ...


@dataclass(frozen=True)
class PluginFactory(Generic[C, T]):
    config: type[C]
    build: Callable[[C, Context], T]

    @property
    def config_model(self) -> type[BaseModel]:
        return self.config

    def create(self, config: Mapping[str, JsonValue], ctx: Context) -> T:
        return self.build(self.config.model_validate(config), ctx)


def factory(config: type[C], build: Callable[[C, Context], T]) -> PluginFactory[C, T]:
    return PluginFactory(config, build)
