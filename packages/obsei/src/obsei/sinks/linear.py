"""Create Linear issues for matching feedback, once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import SECRET
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.routing import Conditions, When
from obsei.sinks._common import SinkConfigError, env, intents, marker, open_issues
from obsei.sources._common import lookup

API_URL = "https://api.linear.app/graphql"
FIND = (
    "query($m: String!) "
    "{ issues(filter: {description: {contains: $m}}, first: 1) { nodes { id } } }"
)
TEAM = "query($id: String!) { team(id: $id) { id } }"
CREATE = (
    "mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id } } }"
)


class LinearConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str = Field(description="Id of the team to create issues in.")
    api_key_env: str = Field(
        default="LINEAR_API_KEY",
        description="Environment variable with a Linear API key.",
        json_schema_extra=SECRET,
    )
    label_ids: list[str] = Field(
        default_factory=list, description="Ids of labels added to each issue."
    )
    when: Conditions = Field(
        default_factory=lambda: intents("bug", "feature_request"),
        description='Which records open an issue, e.g. {"classify.intent": ["bug"]}.',
    )
    max_rating: float | None = Field(default=None, description="Only records rated at most this.")
    max_issues: int = Field(default=10, ge=1, description="Most issues created per run.")


class LinearSink:
    name: ClassVar[str] = "linear"

    def __init__(self, config: LinearConfig, ctx: Context) -> None:
        ctx.egress.check(API_URL)
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)
        self.ctx = ctx
        self.headers = {"Authorization": env(config.api_key_env)}

    def _graphql(self, query: str, variables: dict[str, JsonValue]) -> JsonValue:
        response = self.ctx.http.post(
            API_URL,
            json={"query": query, "variables": variables},
            headers=self.headers,
            extensions=EGRESS,
        )
        response.raise_for_status()
        payload: JsonValue = response.json()
        if isinstance(payload, dict) and payload.get("errors"):
            raise RuntimeError(f"Linear error: {payload['errors']}")
        return payload

    def open_issue(self, title: str, body: str, key: str) -> bool:
        if lookup(self._graphql(FIND, {"m": marker(key)}), "data.issues.nodes"):
            return False
        issue: dict[str, JsonValue] = {
            "teamId": self.config.team_id,
            "title": title,
            "description": f"{body}\n\n<!-- {marker(key)} -->",
        }
        if self.config.label_ids:
            issue["labelIds"] = list(self.config.label_ids)
        self._graphql(CREATE, {"input": issue})
        return True

    def send(self, batch: Sequence[Record]) -> SinkResult:
        return open_issues(self, batch, self.when, self.config.max_issues)

    def verify(self) -> None:
        if not lookup(self._graphql(TEAM, {"id": self.config.team_id}), "data.team.id"):
            raise SinkConfigError(f"no Linear team {self.config.team_id!r}")
