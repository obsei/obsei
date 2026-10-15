"""Built-in sources."""

from obsei.core.plugin import Catalog, factory
from obsei.core.registry import Registry
from obsei.sources.appstore import AppStoreConfig, AppStoreSource
from obsei.sources.appstoreconnect import AppStoreConnectConfig, AppStoreConnectSource
from obsei.sources.bluesky import BlueskyConfig, BlueskySource
from obsei.sources.filedrop import FileDropConfig, FileDropSource
from obsei.sources.files import CsvConfig, CsvSource, FileConfig, JsonlSource
from obsei.sources.github import GitHubIssuesConfig, GitHubIssuesSource
from obsei.sources.gong import GongConfig, GongSource
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

DOCS = "https://docs.obsei.com/guides/sources/"
FIELDS = f"{DOCS}#field-mapping"
GITHUB_TOKENS = (
    "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
    "managing-your-personal-access-tokens"
)


def register(registry: Registry) -> None:
    registry.add_source(
        "csv",
        factory(
            CsvConfig,
            CsvSource,
            Catalog(title="CSV file", category="data", status="verified", docs_url=FIELDS),
        ),
    )
    registry.add_source(
        "jsonl",
        factory(
            FileConfig,
            JsonlSource,
            Catalog(title="JSON Lines file", category="data", docs_url=FIELDS),
        ),
    )
    registry.add_source(
        "rest",
        factory(
            RestConfig,
            RestSource,
            Catalog(
                title="Any JSON API",
                category="data",
                docs_url=f"{DOCS}#recipes-with-the-rest-source",
            ),
        ),
    )
    registry.add_source(
        "appstore",
        factory(
            AppStoreConfig,
            AppStoreSource,
            Catalog(
                title="Apple App Store reviews (public)",
                category="reviews",
                status="verified",
                docs_url=DOCS,
                ask=("countries",),
            ),
        ),
    )
    registry.add_source(
        "playstore",
        factory(
            PlayStoreConfig,
            PlayStoreSource,
            Catalog(
                title="Google Play reviews",
                category="reviews",
                docs_url=DOCS,
                help_url="https://developers.google.com/android-publisher/getting_started",
                ask=("credentials_file",),
            ),
        ),
    )
    registry.add_source(
        "github_issues",
        factory(
            GitHubIssuesConfig,
            GitHubIssuesSource,
            Catalog(
                title="GitHub issues",
                category="issues",
                status="verified",
                docs_url=DOCS,
                help_url=GITHUB_TOKENS,
            ),
        ),
    )
    registry.add_source(
        "rss",
        factory(
            RssConfig,
            RssSource,
            Catalog(title="RSS or Atom feed", category="social", status="verified", docs_url=DOCS),
        ),
    )
    registry.add_source(
        "webhook",
        factory(
            WebhookSourceConfig,
            WebhookSource,
            Catalog(
                title="Webhook intake (obsei serve)",
                category="data",
                docs_url="https://docs.obsei.com/guides/serve/#sending-feedback",
                help_url="https://www.standardwebhooks.com/",
            ),
        ),
    )
    registry.add_source(
        "appstoreconnect",
        factory(
            AppStoreConnectConfig,
            AppStoreConnectSource,
            Catalog(
                title="App Store Connect reviews (your apps)",
                category="reviews",
                docs_url=DOCS,
                help_url="https://developer.apple.com/documentation/appstoreconnectapi/"
                "creating-api-keys-for-app-store-connect-api",
                ask=("private_key_file",),
            ),
        ),
    )
    registry.add_source(
        "hackernews",
        factory(
            HackerNewsConfig,
            HackerNewsSource,
            Catalog(
                title="Hacker News",
                category="social",
                status="verified",
                docs_url=DOCS,
                ask=("query",),
            ),
        ),
    )
    registry.add_source(
        "bluesky",
        factory(
            BlueskyConfig,
            BlueskySource,
            Catalog(
                title="Bluesky posts",
                category="social",
                docs_url=DOCS,
                help_url="https://bsky.app/settings/app-passwords",
            ),
        ),
    )
    registry.add_source(
        "youtube",
        factory(
            YouTubeConfig,
            YouTubeSource,
            Catalog(
                title="YouTube comments",
                category="social",
                docs_url=DOCS,
                help_url="https://developers.google.com/youtube/registering_an_application",
                ask=("video_ids", "channel_id"),
            ),
        ),
    )
    registry.add_source(
        "sql",
        factory(
            SqlConfig,
            SqlSource,
            Catalog(
                title="SQL database or warehouse",
                category="warehouse",
                docs_url=FIELDS,
                help_url="https://docs.sqlalchemy.org/en/20/core/engines.html",
            ),
        ),
    )
    registry.add_source(
        "filedrop",
        factory(
            FileDropConfig,
            FileDropSource,
            Catalog(title="Folder of exports", category="data", docs_url=FIELDS),
        ),
    )
    registry.add_source(
        "imap",
        factory(
            ImapConfig,
            ImapSource,
            Catalog(
                title="Email mailbox (IMAP)",
                category="support",
                docs_url=DOCS,
                help_url="https://support.google.com/accounts/answer/185833",
            ),
        ),
    )
    registry.add_source(
        "mcp",
        factory(
            McpClientConfig,
            McpClientSource,
            Catalog(title="A tool on an MCP server", category="data", docs_url=FIELDS),
        ),
    )
    registry.add_source(
        "zendesk",
        factory(
            ZendeskConfig,
            ZendeskSource,
            Catalog(
                title="Zendesk tickets",
                category="support",
                docs_url=DOCS,
                help_url="https://support.zendesk.com/hc/en-us/articles/"
                "4408889192858-Managing-API-token-access-to-the-Zendesk-API",
            ),
        ),
    )
    registry.add_source(
        "freshdesk",
        factory(
            FreshdeskConfig,
            FreshdeskSource,
            Catalog(
                title="Freshdesk tickets",
                category="support",
                docs_url=DOCS,
                help_url="https://support.freshdesk.com/support/solutions/articles/"
                "215517-how-to-find-your-api-key",
            ),
        ),
    )
    registry.add_source(
        "intercom",
        factory(
            IntercomConfig,
            IntercomSource,
            Catalog(
                title="Intercom conversations",
                category="support",
                docs_url=DOCS,
                help_url="https://developers.intercom.com/docs/build-an-integration/learn-more/"
                "authentication",
                ask=("region",),
            ),
        ),
    )
    registry.add_source(
        "gong",
        factory(
            GongConfig,
            GongSource,
            Catalog(
                title="Gong call transcripts",
                category="support",
                docs_url=DOCS,
                help_url="https://help.gong.io/docs/receive-access-to-the-api",
            ),
        ),
    )


__all__ = ["register"]
