"""Create Linear issues for matching feedback, once per record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import EGRESS, Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.sinks._common import body, env, marker, matches, title
from obsei.sources._common import lookup

API_URL = "https://api.linear.app/graphql"
FIND = (
    "query($m: String!) "
    "{ issues(filter: {description: {contains: $m}}, first: 1) { nodes { id } } }"
)
CREATE = (
    "mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id } } }"
)


class LinearConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str
    api_key_env: str = "LINEAR_API_KEY"
    label_ids: list[str] = Field(default_factory=list)
    when: dict[str, list[str]] = Field(
        default_factory=lambda: {"classify.intent": ["bug", "feature_request"]}
    )
    max_rating: float | None = None
    max_issues: int = Field(default=10, ge=1)


class LinearSink:
    name: ClassVar[str] = "linear"

    def __init__(self, config: LinearConfig, ctx: Context) -> None:
        ctx.egress.check(API_URL)
        self.config = config
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

    def send(self, batch: Sequence[Record]) -> SinkResult:
        selected = [r for r in batch if matches(r, self.config.when, self.config.max_rating)]
        result = SinkResult(skipped=len(batch) - len(selected))
        for record in selected[: self.config.max_issues]:
            found = self._graphql(FIND, {"m": marker(record)})
            nodes = lookup(found, "data.issues.nodes")
            if nodes:
                result.skipped += 1
                continue
            issue: dict[str, JsonValue] = {
                "teamId": self.config.team_id,
                "title": title(record),
                "description": body(record),
            }
            if self.config.label_ids:
                issue["labelIds"] = list(self.config.label_ids)
            try:
                self._graphql(CREATE, {"input": issue})
            except RuntimeError as exc:
                result.errors.append(str(exc))
                break
            result.sent += 1
        result.skipped += max(0, len(selected) - self.config.max_issues)
        return result
