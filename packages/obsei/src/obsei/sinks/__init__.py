"""Built-in sinks."""

from obsei.core.plugin import factory
from obsei.core.registry import Registry
from obsei.sinks.github import GitHubIssueSink, GitHubIssueSinkConfig
from obsei.sinks.parquet import ParquetConfig, ParquetSink
from obsei.sinks.slack import SlackConfig, SlackSink
from obsei.sinks.webhook import WebhookConfig, WebhookSink


def register(registry: Registry) -> None:
    registry.add_sink("webhook", factory(WebhookConfig, WebhookSink))
    registry.add_sink("slack", factory(SlackConfig, SlackSink))
    registry.add_sink("github_issues", factory(GitHubIssueSinkConfig, GitHubIssueSink))
    registry.add_sink("parquet", factory(ParquetConfig, ParquetSink))


__all__ = ["register"]
