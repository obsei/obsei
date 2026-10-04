"""GitHub (or GitHub Enterprise) issues and their comments."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_text, lookup, parse_time, stamp


class GitHubIssuesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    api_url: str = "https://api.github.com"
    token_env: str | None = "GITHUB_TOKEN"  # noqa: S105
    labels: list[str] = Field(default_factory=list)
    state: str = Field(default="all", pattern="^(open|closed|all)$")
    include_comments: bool = False
    max_pages: int = Field(default=20, ge=1)


class GitHubError(RuntimeError):
    pass


class GitHubIssuesSource:
    name: ClassVar[str] = "github_issues"

    def __init__(self, config: GitHubIssuesConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get(config.token_env) if config.token_env else None
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get(self, url: str, params: dict[str, str | int]) -> Iterator[JsonValue]:
        next_url: str | None = url
        for _ in range(self.config.max_pages):
            if next_url is None:
                return
            response = self.ctx.http.get(next_url, params=params or None, headers=self.headers)
            if response.is_error:
                raise GitHubError(f"GitHub API returned {response.status_code} for {next_url}")
            items: JsonValue = response.json()
            if isinstance(items, list):
                yield from items
            next_url = response.links.get("next", {}).get("url")
            params = {}

    def _record(
        self, item: JsonValue, native_id: str, text: str, context: dict[str, str]
    ) -> Record | None:
        created = parse_time(lookup(item, "created_at"))
        if created is None or not text.strip():
            return None
        return Record(
            source=SourceRef(
                type=self.name,
                instance=self.config.repo,
                native_id=native_id,
                url=as_text(lookup(item, "html_url")),
            ),
            text=text.strip(),
            created_at=created,
            author=self.ctx.author(as_text(lookup(item, "user.login"))),
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        since = cursor.get("since") if cursor else None
        params: dict[str, str | int] = {
            "state": c.state,
            "sort": "updated",
            "direction": "asc",
            "per_page": 100,
        }
        if c.labels:
            params["labels"] = ",".join(c.labels)
        if isinstance(since, str):
            params["since"] = since
        newest = since if isinstance(since, str) else None
        for issue in self._get(f"{c.api_url}/repos/{c.repo}/issues", params):
            if lookup(issue, "pull_request") is not None:
                continue
            number = as_text(lookup(issue, "number")) or ""
            updated = as_text(lookup(issue, "updated_at"))
            if updated and (newest is None or updated > newest):
                newest = updated
            labels = lookup(issue, "labels")
            names = (
                [as_text(lookup(label, "name")) for label in labels]
                if isinstance(labels, list)
                else []
            )
            context = {"kind": "issue", "state": as_text(lookup(issue, "state")) or ""}
            if label_text := ", ".join(n for n in names if n):
                context["labels"] = label_text
            title = as_text(lookup(issue, "title")) or ""
            body = as_text(lookup(issue, "body")) or ""
            state: Cursor = {"since": newest}
            record = self._record(issue, number, f"{title}\n\n{body}", context)
            if record is not None:
                yield record, state
            comments_url = as_text(lookup(issue, "comments_url"))
            if c.include_comments and comments_url and lookup(issue, "comments"):
                for comment in self._get(comments_url, {"per_page": 100}):
                    comment_id = as_text(lookup(comment, "id")) or ""
                    note = self._record(
                        comment,
                        f"{number}#comment-{comment_id}",
                        as_text(lookup(comment, "body")) or "",
                        {"kind": "comment", "issue": number},
                    )
                    if note is not None and (not isinstance(since, str) or stamp(note) > since):
                        yield note, state
