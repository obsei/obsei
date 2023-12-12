
def test_imports_all():
    test_core()
    test_sources()
    test_sink()
    test_analyzer()


def test_sources():
    from obsei.source.base_source import BaseSource, BaseSourceConfig
    from obsei.source.appstore_scrapper import AppStoreScrapperSource, AppStoreScrapperConfig
    from obsei.source.email_source import EmailSource, EmailConfig, EmailCredInfo
    from obsei.source.facebook_source import FacebookSource, FacebookSourceConfig, FacebookCredentials
    from obsei.source.google_news_source import GoogleNewsSource, GoogleNewsConfig
    from obsei.source.pandas_source import PandasSource, PandasSourceConfig
    from obsei.source.playstore_reviews import PlayStoreSource, PlayStoreConfig, GoogleCredInfo
    from obsei.source.playstore_scrapper import PlayStoreScrapperSource, PlayStoreScrapperConfig
    from obsei.source.reddit_source import RedditSource, RedditConfig, RedditCredInfo
    from obsei.source.reddit_scrapper import RedditScrapperSource, RedditScrapperConfig
    from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig, TwitterCredentials
    from obsei.source.website_crawler_source import BaseCrawlerConfig, TrafilaturaCrawlerSource, TrafilaturaCrawlerConfig


def test_sink():
    from obsei.sink.base_sink import BaseSink, BaseSinkConfig
    from obsei.sink.dailyget_sink import DailyGetSink, DailyGetSinkConfig, PayloadConvertor
    from obsei.sink.elasticsearch_sink import ElasticSearchSink, ElasticSearchSinkConfig
    from obsei.sink.http_sink import HttpSink, HttpSinkConfig
    from obsei.sink.jira_sink import JiraSink, JiraSinkConfig, JiraPayloadConvertor
    from obsei.sink.logger_sink import LoggerSink, LoggerSinkConfig
    from obsei.sink.pandas_sink import PandasSink, PandasSinkConfig, PandasConvertor
    from obsei.sink.slack_sink import SlackSink, SlackSinkConfig
    from obsei.sink.zendesk_sink import ZendeskSink, ZendeskSinkConfig


def test_analyzer():
    from obsei.analyzer.base_analyzer import BaseAnalyzer, BaseAnalyzerConfig
    from obsei.analyzer.dummy_analyzer import DummyAnalyzer, DummyAnalyzerConfig
    from obsei.analyzer.ner_analyzer import TransformersNERAnalyzer, SpacyNERAnalyzer
    from obsei.analyzer.pii_analyzer import PresidioPIIAnalyzer, PresidioPIIAnalyzerConfig, PresidioAnonymizerConfig, PresidioModelConfig, PresidioEngineConfig
    from obsei.analyzer.sentiment_analyzer import VaderSentimentAnalyzer, TransformersSentimentAnalyzerConfig, TransformersSentimentAnalyzer
    from obsei.analyzer.translation_analyzer import TranslationAnalyzer
    from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig, ZeroShotClassificationAnalyzer, TextClassificationAnalyzer

    from obsei.postprocessor.base_postprocessor import BasePostprocessor, BasePostprocessorConfig
    from obsei.postprocessor.inference_aggregator import InferenceAggregatorConfig, InferenceAggregator
    from obsei.postprocessor.inference_aggregator_function import BaseInferenceAggregateFunction, ClassificationAverageScore, ClassificationMaxCategories

    from obsei.preprocessor.base_preprocessor import BaseTextPreprocessor, BaseTextProcessorConfig
    from obsei.preprocessor.text_cleaner import TextCleaner, TextCleanerConfig
    from obsei.preprocessor.text_splitter import TextSplitter, TextSplitterConfig, TextSplitterPayload
    from obsei.preprocessor.text_tokenizer import BaseTextTokenizer, NLTKTextTokenizer
    from obsei.preprocessor.text_cleaning_function import TextCleaningFunction, ToLowerCase, RemoveStopWords, \
        RemovePunctuation, TokenStemming, RemoveSpecialChars, RemoveWhiteSpaceAndEmptyToken, DecodeUnicode, \
        RemoveDateTime, ReplaceDomainKeywords, RegExSubstitute, SpacyLemmatization


def test_core():
    from obsei.configuration import ObseiConfiguration
    from obsei.payload import BasePayload, TextPayload
    from obsei.processor import Processor

    from obsei.workflow.base_store import BaseStore
    from obsei.workflow.store import WorkflowStore, WorkflowTable
    from obsei.workflow.workflow import Workflow, WorkflowState, WorkflowConfig
