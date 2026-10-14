"""Notify Telegram, Discord, email, Teams and 100+ other services through Apprise. Needs
``pip install 'obsei[notify]'``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.llm.egress import EgressError
from obsei.routing import Conditions, When
from obsei.sinks._common import SinkConfigError, env, title

if TYPE_CHECKING:
    from apprise import NotifyBase


class NotifyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls_env: str = Field(
        default="APPRISE_URLS", description="Environment variable with Apprise URLs."
    )
    when: Conditions = Field(
        default_factory=dict, description='e.g. {"classify.intent": ["bug", "churn_risk"]}'
    )
    max_rating: float | None = None
    max_items: int = Field(default=5, ge=1)


def hosts(plugin: NotifyBase) -> list[str]:
    """The hosts an Apprise service connects to, as far as obsei can tell: a fixed API host,
    the SMTP server of email, and the host named in the URL."""
    found = []
    fixed = getattr(plugin, "notify_url", None)
    fixed_host = urlsplit(fixed).hostname if isinstance(fixed, str) else None
    if fixed_host and "{" not in fixed_host:
        found.append(fixed_host)
    smtp_host = getattr(plugin, "smtp_host", None)
    if smtp_host:
        found.append(smtp_host)
    elif plugin.host and "." in plugin.host:
        found.append(plugin.host)
    return found


class NotifySink:
    name: ClassVar[str] = "notify"

    def __init__(self, config: NotifyConfig, ctx: Context) -> None:
        try:
            import apprise  # noqa: PLC0415
        except ImportError:
            raise SinkConfigError("the notify sink needs: pip install 'obsei[notify]'") from None
        targets = apprise.Apprise()
        if not targets.add(env(config.urls_env)):
            raise SinkConfigError(f"{config.urls_env} holds an invalid Apprise URL")
        self.targets = list(targets)
        for target in self.targets:
            found = hosts(target)
            if not found and ctx.egress.mode != "hybrid":
                raise EgressError(
                    f"cannot tell which host {target.service_name} connects to; "
                    "notify sinks for it need hybrid egress mode"
                )
            for host in found:
                ctx.egress.check(f"https://{host}")
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)

    def send(self, batch: Sequence[Record]) -> SinkResult:
        selected = [r for r in batch if self.when.matches(r)]
        if not selected:
            return SinkResult(skipped=len(batch))
        lines = [
            f"- {title(r)}" + (f"\n  {r.source.url}" if r.source.url else "")
            for r in selected[: self.config.max_items]
        ]
        if len(selected) > self.config.max_items:
            lines.append(f"…and {len(selected) - self.config.max_items} more.")
        heading = f"obsei: {len(selected)} matching feedback item(s)"
        body = "\n".join(lines)
        failed = [
            str(t.service_name) for t in self.targets if not t.notify(body=body, title=heading)
        ]
        if failed:
            return SinkResult(errors=[f"notify failed for {', '.join(failed)}"])
        return SinkResult(sent=len(selected), skipped=len(batch) - len(selected))
