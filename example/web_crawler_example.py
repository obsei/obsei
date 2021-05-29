# Fetch full news article
from obsei.source.website_crawler_source import (
    TrafilaturaCrawlerConfig,
    TrafilaturaCrawlerSource,
)


def print_list(response_list):
    for response in response_list:
        print(response.__dict__)


# Single URL
source_config = TrafilaturaCrawlerConfig(urls=["https://lalitpagaria.github.io/obsei/"])

source = TrafilaturaCrawlerSource()

source_response_list = source.lookup(source_config)
print_list(source_response_list)


# RSS feed (Note it will take lot of time)
source_config = TrafilaturaCrawlerConfig(
    urls=["https://news.google.com/rss/search?q=bitcoin&hl=en&gl=US&ceid=US:en"],
    is_feed=True,
)

source = TrafilaturaCrawlerSource()

source_response_list = source.lookup(source_config)
print_list(source_response_list)


# Full website (Note it will take lot of time)
source_config = TrafilaturaCrawlerConfig(
    urls=["https://haystack.deepset.ai/"],
    is_sitemap=True,
)

source = TrafilaturaCrawlerSource()

source_response_list = source.lookup(source_config)
print_list(source_response_list)
