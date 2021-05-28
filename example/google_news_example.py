from obsei.source.google_news_source import GoogleNewsConfig, GoogleNewsSource

# Only fetch title and highlight
source_config_without_full_text = GoogleNewsConfig(
    query="bitcoin",
    max_results=5,
    lookup_period="1d",
)

# Fetch full news article
source_config_with_full_text = GoogleNewsConfig(
    query="bitcoin",
    max_results=5,
    fetch_article=True,
    lookup_period="1d",
)

source = GoogleNewsSource()

news_articles_without_full_text = source.lookup(source_config_without_full_text)

news_articles_with_full_text = source.lookup(source_config_with_full_text)

for article in news_articles_without_full_text:
    print(article.__dict__)

for article in news_articles_with_full_text:
    print(article.__dict__)
