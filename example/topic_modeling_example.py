from obsei.analyzer.topic_analyzer import TopicClassificationAnalyzer, TopicAnalyzerConfig
from obsei.source.google_news_source import GoogleNewsConfig, GoogleNewsSource

source_config = GoogleNewsConfig(
    query="bitcoin",
    max_results=5,
    fetch_article=True,
    lookup_period="1d",
)

source = GoogleNewsSource()

analyzer_config = TopicAnalyzerConfig(
    labels=["LDA", "BERT", "LDA_BERT"],
)

text_analyzer = TopicClassificationAnalyzer(
    model_name_or_path="sentence-transformers/distiluse-base-multilingual-cased", device="auto"
)


news_articles = source.lookup(source_config)


analyzer_responses = text_analyzer.analyze_input(
    source_response_list=news_articles, analyzer_config=analyzer_config
)

for article in news_articles:
    print(article.__dict__)

for response in analyzer_responses:
    print(response.__dict__)
