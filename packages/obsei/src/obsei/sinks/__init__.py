"""Built-in sinks."""

from obsei.core.plugin import Catalog, factory
from obsei.core.registry import Registry
from obsei.sinks.github import GitHubIssueSink, GitHubIssueSinkConfig
from obsei.sinks.jira import JiraConfig, JiraSink
from obsei.sinks.linear import LinearConfig, LinearSink
from obsei.sinks.notify import NotifyConfig, NotifySink
from obsei.sinks.parquet import ParquetConfig, ParquetSink
from obsei.sinks.slack import SlackConfig, SlackSink
from obsei.sinks.sql import SqlSink, SqlSinkConfig
from obsei.sinks.webhook import WebhookConfig, WebhookSink

DOCS = "https://docs.obsei.com/guides/sinks/"
GITHUB_TOKENS = (
    "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
    "managing-your-personal-access-tokens"
)


def register(registry: Registry) -> None:
    registry.add_sink(
        "webhook",
        factory(
            WebhookConfig,
            WebhookSink,
            Catalog(
                title="Signed webhook (CloudEvents)",
                category="notify",
                docs_url=f"{DOCS}#webhooks",
                help_url="https://www.standardwebhooks.com/",
            ),
        ),
    )
    registry.add_sink(
        "slack",
        factory(
            SlackConfig,
            SlackSink,
            Catalog(
                title="Slack channel",
                category="chat",
                status="verified",
                docs_url=DOCS,
                help_url="https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/",
            ),
        ),
    )
    registry.add_sink(
        "github_issues",
        factory(
            GitHubIssueSinkConfig,
            GitHubIssueSink,
            Catalog(
                title="GitHub issues", category="issues", docs_url=DOCS, help_url=GITHUB_TOKENS
            ),
        ),
    )
    registry.add_sink(
        "parquet",
        factory(
            ParquetConfig,
            ParquetSink,
            Catalog(title="Parquet files", category="warehouse", docs_url=DOCS),
        ),
    )
    registry.add_sink(
        "jira",
        factory(
            JiraConfig,
            JiraSink,
            Catalog(
                title="Jira issues",
                category="issues",
                docs_url=DOCS,
                help_url="https://support.atlassian.com/atlassian-account/docs/"
                "manage-api-tokens-for-your-atlassian-account/",
            ),
        ),
    )
    registry.add_sink(
        "linear",
        factory(
            LinearConfig,
            LinearSink,
            Catalog(
                title="Linear issues",
                category="issues",
                status="verified",
                docs_url=DOCS,
                help_url="https://linear.app/docs/api-and-webhooks",
            ),
        ),
    )
    registry.add_sink(
        "sql",
        factory(
            SqlSinkConfig,
            SqlSink,
            Catalog(
                title="SQL database or warehouse",
                category="warehouse",
                docs_url=DOCS,
                help_url="https://docs.sqlalchemy.org/en/20/core/engines.html",
            ),
        ),
    )
    registry.add_sink(
        "notify",
        factory(
            NotifyConfig,
            NotifySink,
            Catalog(
                title="Telegram, Discord, email and 100+ services (Apprise)",
                category="notify",
                docs_url=f"{DOCS}#notifications",
                help_url="https://github.com/caronc/apprise/wiki",
            ),
        ),
    )


__all__ = ["register"]
