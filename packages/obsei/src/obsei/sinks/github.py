"""Open GitHub issues for matching feedback, once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import EGRESS, Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.routing import Conditions, When
from obsei.sinks._common import env, intents, marker, open_issues


class GitHubIssueSinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    api_url: str = "https://api.github.com"
    token_env: str = "GITHUB_TOKEN"  # noqa: S105
    labels: list[str] = Field(default_factory=lambda: ["feedback"])
    when: Conditions = Field(default_factory=lambda: intents("bug", "feature_request"))
    max_rating: float | None = None
    max_issues: int = Field(default=10, ge=1)


class GitHubIssueSink:
    name: ClassVar[str] = "github_issues"

    def __init__(self, config: GitHubIssueSinkConfig, ctx: Context) -> None:
        ctx.egress.check(config.api_url)
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)
        self.ctx = ctx
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {env(config.token_env)}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _exists(self, key: str) -> bool:
        query = f'repo:{self.config.repo} is:issue in:body "{marker(key)}"'
        response = self.ctx.http.get(
            f"{self.config.api_url}/search/issues",
            params={"q": query},
            headers=self.headers,
            extensions=EGRESS,
        )
        response.raise_for_status()
        count = response.json().get("total_count", 0)
        return isinstance(count, int) and count > 0

    def open_issue(self, title: str, body: str, key: str) -> bool:
        if self._exists(key):
            return False
        response = self.ctx.http.post(
            f"{self.config.api_url}/repos/{self.config.repo}/issues",
            json={
                "title": title,
                "body": f"{body}\n\n<!-- {marker(key)} -->",
                "labels": self.config.labels,
            },
            headers=self.headers,
            extensions=EGRESS,
        )
        if response.is_error:
            raise RuntimeError(f"GitHub returned {response.status_code}")
        return True

    def send(self, batch: Sequence[Record]) -> SinkResult:
        return open_issues(self, batch, self.when, self.config.max_issues)


__all__ = ["GitHubIssueSink", "GitHubIssueSinkConfig"]
