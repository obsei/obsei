"""Open GitHub issues for matching feedback, once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.sinks._common import env, label, matches


class GitHubIssueSinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    api_url: str = "https://api.github.com"
    token_env: str = "GITHUB_TOKEN"  # noqa: S105
    labels: list[str] = Field(default_factory=lambda: ["feedback"])
    when: dict[str, list[str]] = Field(
        default_factory=lambda: {"classify.intent": ["bug", "feature_request"]}
    )
    max_rating: float | None = None
    max_issues: int = Field(default=10, ge=1)


TITLE_LENGTH = 80


def marker(record: Record) -> str:
    return f"obsei:{record.id}"


def title(record: Record) -> str:
    first = record.text.strip().splitlines()[0] if record.text.strip() else record.id
    intent = label(record, "classify.intent")
    prefix = f"[{intent}] " if intent else ""
    return prefix + (first[:TITLE_LENGTH] + "…" if len(first) > TITLE_LENGTH else first)


def body(record: Record) -> str:
    lines = [f"> {line}" for line in record.text.splitlines()]
    meta = [f"source: `{record.source.type}/{record.source.instance}`"]
    if record.rating is not None:
        meta.append(f"rating: {record.rating:g}")
    if record.source.url:
        meta.append(f"[original]({record.source.url})")
    return "\n".join([*lines, "", " · ".join(meta), "", f"<!-- {marker(record)} -->"])


class GitHubIssueSink:
    name: ClassVar[str] = "github_issues"

    def __init__(self, config: GitHubIssueSinkConfig, ctx: Context) -> None:
        ctx.egress.check(config.api_url)
        self.config = config
        self.ctx = ctx
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {env(config.token_env)}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _exists(self, record: Record) -> bool:
        query = f'repo:{self.config.repo} is:issue in:body "{marker(record)}"'
        response = self.ctx.http.get(
            f"{self.config.api_url}/search/issues", params={"q": query}, headers=self.headers
        )
        response.raise_for_status()
        count = response.json().get("total_count", 0)
        return isinstance(count, int) and count > 0

    def send(self, batch: Sequence[Record]) -> SinkResult:
        selected = [r for r in batch if matches(r, self.config.when, self.config.max_rating)]
        result = SinkResult(skipped=len(batch) - len(selected))
        for record in selected[: self.config.max_issues]:
            if self._exists(record):
                result.skipped += 1
                continue
            response = self.ctx.http.post(
                f"{self.config.api_url}/repos/{self.config.repo}/issues",
                json={"title": title(record), "body": body(record), "labels": self.config.labels},
                headers=self.headers,
            )
            if response.is_error:
                result.errors.append(f"GitHub returned {response.status_code}")
                break
            result.sent += 1
        result.skipped += max(0, len(selected) - self.config.max_issues)
        return result


__all__ = ["GitHubIssueSink", "GitHubIssueSinkConfig"]
