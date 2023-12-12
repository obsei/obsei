from obsei.analyzer.classification_analyzer import (
    ClassificationAnalyzerConfig,
    ZeroShotClassificationAnalyzer,
)
from obsei.source.google_news_source import GoogleNewsConfig, GoogleNewsSource

# Only fetch title and highlight
source_config_without_full_text = GoogleNewsConfig(
    query="bitcoin",
    max_results=150,
    after_date='2021-10-01',
    before_date='2021-10-31',
)

# Fetch full news article
source_config_with_full_text = GoogleNewsConfig(
    query="bitcoin",
    max_results=5,
    fetch_article=True,
    lookup_period="1d",
    # proxy="http://127.0.0.1:8080"
)

source = GoogleNewsSource()

analyzer_config = ClassificationAnalyzerConfig(
    labels=["buy", "sell", "going up", "going down"],
)

text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli", device="auto"
)

news_articles_without_full_text = source.lookup(source_config_without_full_text)

news_articles_with_full_text = source.lookup(source_config_with_full_text)


analyzer_responses_without_full_text = text_analyzer.analyze_input(
    source_response_list=news_articles_without_full_text,
    analyzer_config=analyzer_config,
)

analyzer_responses_with_full_text = text_analyzer.analyze_input(
    source_response_list=news_articles_with_full_text, analyzer_config=analyzer_config
)

for article in news_articles_without_full_text:
    print(article.__dict__)

for response in analyzer_responses_without_full_text:
    print(response.__dict__)

for article in news_articles_with_full_text:
    print(article.__dict__)

for response in analyzer_responses_with_full_text:
    print(response.__dict__)
