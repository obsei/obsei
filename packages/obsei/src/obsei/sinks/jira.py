"""Create Jira issues for matching feedback (Jira Cloud or Data Center), once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import SECRET
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.routing import Conditions, When
from obsei.sinks._common import SinkConfigError, env, intents, open_issues


class JiraConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(description="https://your-site.atlassian.net or your Data Center URL")
    project_key: str = Field(
        pattern=r"^[A-Z][A-Z0-9_]+$",
        description="Key of the project to create issues in, e.g. APP.",
    )
    issue_type: str = Field(default="Bug", description="Issue type to create.")
    auth: Literal["basic", "bearer"] = Field(
        default="basic",
        description="basic (Cloud: email and API token) or bearer (Data Center access token).",
    )
    email_env: str = Field(
        default="JIRA_EMAIL",
        description="Environment variable with your Atlassian account email (basic auth).",
        json_schema_extra=SECRET,
    )
    token_env: str = Field(
        default="JIRA_API_TOKEN",
        description="Environment variable with the API token or personal access token.",
        json_schema_extra=SECRET,
    )
    api_version: Literal["2", "3"] = Field(
        default="3", description="REST API version: 3 for Cloud, 2 for Data Center."
    )
    labels: list[str] = Field(
        default_factory=lambda: ["feedback"], description="Labels added to each issue."
    )
    when: Conditions = Field(
        default_factory=lambda: intents("bug", "feature_request"),
        description='Which records open an issue, e.g. {"classify.intent": ["bug"]}.',
    )
    max_rating: float | None = Field(default=None, description="Only records rated at most this.")
    max_issues: int = Field(default=10, ge=1, description="Most issues created per run.")


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

    def verify(self) -> None:
        url = f"{self.api}/project/{self.config.project_key}"
        response = self.ctx.http.get(
            url,
            headers=self.headers,
            auth=self.auth or httpx.USE_CLIENT_DEFAULT,
            extensions=EGRESS,
        )
        if response.is_error:
            raise SinkConfigError(f"Jira returned {response.status_code} for {url}")
