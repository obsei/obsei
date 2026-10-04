"""Built-in sources."""

from obsei.core.plugin import factory
from obsei.core.registry import Registry
from obsei.sources.appstore import AppStoreConfig, AppStoreSource
from obsei.sources.appstoreconnect import AppStoreConnectConfig, AppStoreConnectSource
from obsei.sources.bluesky import BlueskyConfig, BlueskySource
from obsei.sources.filedrop import FileDropConfig, FileDropSource
from obsei.sources.files import CsvConfig, CsvSource, FileConfig, JsonlSource
from obsei.sources.github import GitHubIssuesConfig, GitHubIssuesSource
from obsei.sources.hackernews import HackerNewsConfig, HackerNewsSource
from obsei.sources.helpdesk import (
    FreshdeskConfig,
    FreshdeskSource,
    IntercomConfig,
    IntercomSource,
    ZendeskConfig,
    ZendeskSource,
)
from obsei.sources.imap import ImapConfig, ImapSource
from obsei.sources.mcp_client import McpClientConfig, McpClientSource
from obsei.sources.playstore import PlayStoreConfig, PlayStoreSource
from obsei.sources.rest import RestConfig, RestSource
from obsei.sources.rss import RssConfig, RssSource
from obsei.sources.sql import SqlConfig, SqlSource
from obsei.sources.webhook import WebhookSource, WebhookSourceConfig
from obsei.sources.youtube import YouTubeConfig, YouTubeSource


def register(registry: Registry) -> None:
    registry.add_source("csv", factory(CsvConfig, CsvSource))
    registry.add_source("jsonl", factory(FileConfig, JsonlSource))
    registry.add_source("rest", factory(RestConfig, RestSource))
    registry.add_source("appstore", factory(AppStoreConfig, AppStoreSource))
    registry.add_source("playstore", factory(PlayStoreConfig, PlayStoreSource))
    registry.add_source("github_issues", factory(GitHubIssuesConfig, GitHubIssuesSource))
    registry.add_source("rss", factory(RssConfig, RssSource))
    registry.add_source("webhook", factory(WebhookSourceConfig, WebhookSource))
    registry.add_source("appstoreconnect", factory(AppStoreConnectConfig, AppStoreConnectSource))
    registry.add_source("hackernews", factory(HackerNewsConfig, HackerNewsSource))
    registry.add_source("bluesky", factory(BlueskyConfig, BlueskySource))
    registry.add_source("youtube", factory(YouTubeConfig, YouTubeSource))
    registry.add_source("sql", factory(SqlConfig, SqlSource))
    registry.add_source("filedrop", factory(FileDropConfig, FileDropSource))
    registry.add_source("imap", factory(ImapConfig, ImapSource))
    registry.add_source("mcp", factory(McpClientConfig, McpClientSource))
    registry.add_source("zendesk", factory(ZendeskConfig, ZendeskSource))
    registry.add_source("freshdesk", factory(FreshdeskConfig, FreshdeskSource))
    registry.add_source("intercom", factory(IntercomConfig, IntercomSource))


__all__ = ["register"]
