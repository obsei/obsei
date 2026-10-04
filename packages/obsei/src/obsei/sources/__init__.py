"""Built-in sources."""

from obsei.core.plugin import factory
from obsei.core.registry import Registry
from obsei.sources.appstore import AppStoreConfig, AppStoreSource
from obsei.sources.files import CsvConfig, CsvSource, FileConfig, JsonlSource
from obsei.sources.github import GitHubIssuesConfig, GitHubIssuesSource
from obsei.sources.playstore import PlayStoreConfig, PlayStoreSource
from obsei.sources.rest import RestConfig, RestSource
from obsei.sources.rss import RssConfig, RssSource


def register(registry: Registry) -> None:
    registry.add_source("csv", factory(CsvConfig, CsvSource))
    registry.add_source("jsonl", factory(FileConfig, JsonlSource))
    registry.add_source("rest", factory(RestConfig, RestSource))
    registry.add_source("appstore", factory(AppStoreConfig, AppStoreSource))
    registry.add_source("playstore", factory(PlayStoreConfig, PlayStoreSource))
    registry.add_source("github_issues", factory(GitHubIssuesConfig, GitHubIssuesSource))
    registry.add_source("rss", factory(RssConfig, RssSource))


__all__ = ["register"]
