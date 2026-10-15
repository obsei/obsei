"""Open GitHub issues for matching feedback, once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import SECRET
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.routing import Conditions, When
from obsei.sinks._common import SinkConfigError, env, intents, marker, open_issues


class GitHubIssueSinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str = Field(
        pattern=r"^[\w.-]+/[\w.-]+$", description="owner/name of the repository to open issues in."
    )
    api_url: str = Field(
        default="https://api.github.com",
        description="API URL; change it for GitHub Enterprise Server.",
    )
    token_env: str = Field(
        default="GITHUB_TOKEN",
        description="Environment variable with a token that can create issues.",
        json_schema_extra=SECRET,
    )
    labels: list[str] = Field(
        default_factory=lambda: ["feedback"], description="Labels added to each issue."
    )
    when: Conditions = Field(
        default_factory=lambda: intents("bug", "feature_request"),
        description='Which records open an issue, e.g. {"classify.intent": ["bug"]}.',
    )
    max_rating: float | None = Field(default=None, description="Only records rated at most this.")
    max_issues: int = Field(default=10, ge=1, description="Most issues opened per run.")


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

    def verify(self) -> None:
        url = f"{self.config.api_url}/repos/{self.config.repo}"
        response = self.ctx.http.get(url, headers=self.headers, extensions=EGRESS)
        if response.is_error:
            raise SinkConfigError(f"GitHub returned {response.status_code} for {url}")


__all__ = ["GitHubIssueSink", "GitHubIssueSinkConfig"]
