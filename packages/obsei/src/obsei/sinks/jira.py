"""Create Jira issues for matching feedback (Jira Cloud or Data Center), once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import EGRESS, Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.routing import Conditions, When
from obsei.sinks._common import env, intents, open_issues


class JiraConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(description="https://your-site.atlassian.net or your Data Center URL")
    project_key: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    issue_type: str = "Bug"
    auth: Literal["basic", "bearer"] = "basic"
    email_env: str = "JIRA_EMAIL"
    token_env: str = "JIRA_API_TOKEN"  # noqa: S105
    api_version: Literal["2", "3"] = "3"
    labels: list[str] = Field(default_factory=lambda: ["feedback"])
    when: Conditions = Field(default_factory=lambda: intents("bug", "feature_request"))
    max_rating: float | None = None
    max_issues: int = Field(default=10, ge=1)


def dedupe_label(key: str) -> str:
    return f"obsei-{key}"


def adf(text: str) -> dict[str, JsonValue]:
    paragraphs: list[JsonValue] = [
        {"type": "paragraph", "content": [{"type": "text", "text": block}]}
        for block in text.split("\n\n")
        if block.strip()
    ]
    return {"type": "doc", "version": 1, "content": paragraphs}


class JiraSink:
    name: ClassVar[str] = "jira"

    def __init__(self, config: JiraConfig, ctx: Context) -> None:
        ctx.egress.check(config.base_url)
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)
        self.ctx = ctx
        self.api = f"{config.base_url.rstrip('/')}/rest/api/{config.api_version}"
        token = env(config.token_env)
        self.auth: httpx.Auth | None = None
        self.headers = {"Accept": "application/json"}
        if config.auth == "basic":
            self.auth = httpx.BasicAuth(env(config.email_env), token)
        else:
            self.headers["Authorization"] = f"Bearer {token}"

    def _exists(self, key: str) -> bool:
        jql = f'project = "{self.config.project_key}" AND labels = "{dedupe_label(key)}"'
        path = "/search/jql" if self.config.api_version == "3" else "/search"
        response = self.ctx.http.get(
            self.api + path,
            params={"jql": jql, "maxResults": 1, "fields": "key"},
            headers=self.headers,
            auth=self.auth or httpx.USE_CLIENT_DEFAULT,
            extensions=EGRESS,
        )
        response.raise_for_status()
        issues = response.json().get("issues", [])
        return isinstance(issues, list) and bool(issues)

    def open_issue(self, title: str, body: str, key: str) -> bool:
        if self._exists(key):
            return False
        fields: dict[str, JsonValue] = {
            "project": {"key": self.config.project_key},
            "issuetype": {"name": self.config.issue_type},
            "summary": title,
            "description": adf(body) if self.config.api_version == "3" else body,
            "labels": [*self.config.labels, dedupe_label(key)],
        }
        response = self.ctx.http.post(
            f"{self.api}/issue",
            json={"fields": fields},
            headers=self.headers,
            auth=self.auth or httpx.USE_CLIENT_DEFAULT,
            extensions=EGRESS,
        )
        if response.is_error:
            raise RuntimeError(f"Jira returned {response.status_code}")
        return True

    def send(self, batch: Sequence[Record]) -> SinkResult:
        return open_issues(self, batch, self.when, self.config.max_issues)
