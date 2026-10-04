"""Pull feedback from any MCP server's tool (CRM, data platform, internal agents).

Needs ``pip install 'obsei[mcp]'``. The tool's structured result (or JSON text) is mapped with
``fields``; ``since_argument`` receives the newest timestamp seen for incremental pulls.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, TypeAlias

import anyio
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, lookup, map_item, stamp

if TYPE_CHECKING:
    from mcp.client.stdio import StdioServerParameters
    from mcp.server.mcpserver import MCPServer

    Target: TypeAlias = MCPServer | StdioServerParameters | str


class McpClientConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: list[str] | None = Field(default=None, description="Launch over stdio.")
    url: str | None = Field(default=None, description="Streamable HTTP endpoint.")
    env: dict[str, str] = Field(
        default_factory=dict, description="Child env: variable name to obsei env variable."
    )
    tool: str
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    since_argument: str | None = None
    items_path: str | None = None
    instance: str = "default"
    fields: FieldMap = Field(default_factory=FieldMap)

    @model_validator(mode="after")
    def _one_target(self) -> McpClientConfig:
        if (self.command is None) == (self.url is None):
            raise ValueError("set exactly one of command or url")
        return self


class McpClientError(RuntimeError):
    pass


class McpClientSource:
    name: ClassVar[str] = "mcp"

    def __init__(self, config: McpClientConfig, ctx: Context) -> None:
        if config.url:
            ctx.egress.check(config.url)
        self.config = config
        self.ctx = ctx
        self.server: MCPServer | None = None

    def _target(self) -> Target:
        if self.server is not None:
            return self.server
        if self.config.url:
            return self.config.url
        from mcp.client.stdio import StdioServerParameters  # noqa: PLC0415

        command = self.config.command or []
        env = {k: os.environ.get(v, "") for k, v in self.config.env.items()}
        return StdioServerParameters(command=command[0], args=command[1:], env=env or None)

    async def _call(self, arguments: dict[str, JsonValue]) -> JsonValue:
        try:
            from mcp.client import Client  # noqa: PLC0415
            from mcp.types import TextContent  # noqa: PLC0415
        except ImportError:
            raise McpClientError("the mcp source needs: pip install 'obsei[mcp]'") from None
        async with Client(self._target()) as client:
            result = await client.call_tool(self.config.tool, arguments)
        if result.is_error:
            raise McpClientError(f"tool {self.config.tool!r} failed")
        structured: JsonValue = result.structured_content
        if structured is not None:
            return structured
        texts = [c.text for c in result.content if isinstance(c, TextContent)]
        try:
            parsed: JsonValue = json.loads("".join(texts)) if texts else None
        except json.JSONDecodeError:
            raise McpClientError(f"tool {self.config.tool!r} did not return JSON") from None
        return parsed

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        seen = cursor.get("since") if cursor else None
        arguments = dict(c.arguments)
        if c.since_argument and isinstance(seen, str):
            arguments[c.since_argument] = seen
        payload = anyio.run(self._call, arguments)
        items = lookup(payload, c.items_path) if c.items_path else payload
        newest = seen if isinstance(seen, str) else None
        now = datetime.now(UTC)
        for item in items if isinstance(items, list) else []:
            record = map_item(
                item,
                c.fields,
                source_type=self.name,
                instance=c.instance,
                ctx=self.ctx,
                default_time=now,
            )
            if record is None:
                continue
            newest = max(newest, stamp(record)) if newest else stamp(record)
            yield record, {"since": newest}
