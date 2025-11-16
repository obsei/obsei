# Obsei Component Reference Guide

A comprehensive reference for all Obsei components, their configurations, and usage examples.

---

## Table of Contents

1. [Sources (Observers)](#sources-observers)
2. [Analyzers](#analyzers)
3. [Sinks (Informers)](#sinks-informers)
4. [Preprocessors](#preprocessors)
5. [Postprocessors](#postprocessors)
6. [Utility Components](#utility-components)

---

## Sources (Observers)

### Twitter Source

**Module**: `obsei.source.twitter_source`

**Purpose**: Fetch tweets by keywords, hashtags, or user mentions

**Configuration**:
```python
from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig, TwitterCredentials

source_config = TwitterSourceConfig(
    keywords=["#product", "@company", "keyword"],  # Search terms
    lookup_period="1h",                            # Time window: <number><d|h|m>
    cred_info=TwitterCredentials(
        consumer_key="<key>",
        consumer_secret="<secret>",
        bearer_token="<token>"                     # Required for API v2
    ),
    max_results=100                                 # Max tweets per request
)

source = TwitterSource()
results = source.lookup(source_config)
```

**Authentication**: Requires Twitter Developer Account and Bearer Token

**Rate Limits**: 450 requests per 15-minute window (user context)

---

### Reddit Source (API)

**Module**: `obsei.source.reddit_source`

**Purpose**: Fetch posts and comments from subreddits using official API

**Configuration**:
```python
from obsei.source.reddit_source import RedditSource, RedditConfig, RedditCredInfo

source_config = RedditConfig(
    subreddits=["python", "MachineLearning"],      # List of subreddits
    lookup_period="1h",
    cred_info=RedditCredInfo(
        username="<username>",
        password="<password>",
        client_id="<client_id>",                   # Optional
        client_secret="<client_secret>",           # Optional
        refresh_token="<refresh_token>"            # Optional
    ),
    post_limit=100,                                # Posts per subreddit
    comment_limit=100                              # Comments per post
)

source = RedditSource()
```

**Authentication Modes**:
- Password Flow (username/password)
- Read-Only Mode (no credentials)
- Saved Refresh Token

---

### Reddit Scraper

**Module**: `obsei.source.reddit_scrapper`

**Purpose**: Scrape Reddit via RSS feeds (no API credentials needed)

**Configuration**:
```python
from obsei.source.reddit_scrapper import RedditScrapperSource, RedditScrapperConfig

source_config = RedditScrapperConfig(
    url="https://www.reddit.com/r/python/comments/.rss?sort=new",
    lookup_period="6h"
)

source = RedditScrapperSource()
```

**Note**: Heavily rate-limited, use for small-scale scraping only

---

### Play Store Scraper

**Module**: `obsei.source.playstore_scrapper`

**Purpose**: Scrape app reviews from Google Play Store

**Configuration**:
```python
from obsei.source.playstore_scrapper import PlayStoreScrapperSource, PlayStoreScrapperConfig

source_config = PlayStoreScrapperConfig(
    app_url='https://play.google.com/store/apps/details?id=com.app.id',
    # OR
    package_name='com.app.id',
    countries=["us", "uk"],                        # Country codes
    max_count=100,                                 # Max reviews
    lookup_period="7d"
)

source = PlayStoreScrapperSource()
```

**No Authentication Required**

---

### Play Store Reviews (Official API)

**Module**: `obsei.source.playstore_reviews`

**Purpose**: Fetch reviews using Google Play Developer API

**Configuration**:
```python
from obsei.source.playstore_reviews import PlayStoreReviewsSource, PlayStoreReviewsConfig

source_config = PlayStoreReviewsConfig(
    package_name="com.app.id",
    credentials_json="path/to/credentials.json",   # Service account JSON
    max_results=1000
)

source = PlayStoreReviewsSource()
```

**Authentication**: Requires Google Cloud Service Account

---

### App Store Scraper

**Module**: `obsei.source.appstore_scrapper`

**Purpose**: Scrape app reviews from Apple App Store

**Configuration**:
```python
from obsei.source.appstore_scrapper import AppStoreScrapperSource, AppStoreScrapperConfig

source_config = AppStoreScrapperConfig(
    app_id="310633997",                            # From App Store URL
    countries=["us", "gb"],
    lookup_period="7d",
    max_count=100
)

source = AppStoreScrapperSource()
```

**No Authentication Required**

---

### Facebook Source

**Module**: `obsei.source.facebook_source`

**Purpose**: Fetch page posts and comments

**Configuration**:
```python
from obsei.source.facebook_source import FacebookSource, FacebookSourceConfig, FacebookCredentials

source_config = FacebookSourceConfig(
    page_id="110844591144719",                     # Facebook page ID
    lookup_period="1h",
    cred_info=FacebookCredentials(
        app_id="<app_id>",
        app_secret="<app_secret>",
        long_term_token="<token>"                  # Long-lived user token
    )
)

source = FacebookSource()
```

**Authentication**: Requires Facebook App and long-term user token

---

### Email Source

**Module**: `obsei.source.email_source`

**Purpose**: Monitor IMAP email inbox

**Configuration**:
```python
from obsei.source.email_source import EmailSource, EmailConfig, EmailCredInfo

source_config = EmailConfig(
    imap_server="imap.gmail.com",
    cred_info=EmailCredInfo(
        username="user@example.com",
        password="<password>"                      # App-specific password for Gmail
    ),
    lookup_period="1h",
    folder="INBOX",                                # Email folder
    subject_filter="Support Request"               # Optional filter
)

source = EmailSource()
```

**Gmail Setup**: Enable IMAP and use app-specific password

---

### Google News Source

**Module**: `obsei.source.google_news_source`

**Purpose**: Fetch news articles by query

**Configuration**:
```python
from obsei.source.google_news_source import GoogleNewsSource, GoogleNewsConfig

source_config = GoogleNewsConfig(
    query="artificial intelligence",
    max_results=10,
    fetch_article=True,                            # Fetch full article text
    lang="en",
    country="US",
    period="7d"                                    # Time period
)

source = GoogleNewsSource()
```

**No Authentication Required**

---

### Google Maps Reviews

**Module**: `obsei.source.google_maps_reviews`

**Purpose**: Fetch location reviews via Outscraper API

**Configuration**:
```python
from obsei.source.google_maps_reviews import OSGoogleMapsReviewsSource, OSGoogleMapsReviewsConfig

source_config = OSGoogleMapsReviewsConfig(
    api_key="<outscraper_api_key>",
    queries=["ChIJN1t_tDeuEmsRUsoyG83frY4"],      # Place IDs or URLs
    number_of_reviews=100
)

source = OSGoogleMapsReviewsSource()
```

**Authentication**: Requires Outscraper API key

---

### YouTube Scraper

**Module**: `obsei.source.youtube_scrapper`

**Purpose**: Scrape video comments

**Configuration**:
```python
from obsei.source.youtube_scrapper import YoutubeScrapperSource, YoutubeScrapperConfig

source_config = YoutubeScrapperConfig(
    video_url="https://www.youtube.com/watch?v=VIDEO_ID",
    fetch_replies=True,
    max_comments=100,
    lookup_period="7d"
)

source = YoutubeScrapperSource()
```

**No Authentication Required**

---

### Website Crawler

**Module**: `obsei.source.website_crawler_source`

**Purpose**: Extract text from web pages

**Configuration**:
```python
from obsei.source.website_crawler_source import TrafilaturaCrawlerSource, TrafilaturaCrawlerConfig

source_config = TrafilaturaCrawlerConfig(
    urls=['https://example.com', 'https://example.com/page2']
)

source = TrafilaturaCrawlerSource()
```

**Note**: Requires `trafilatura` package (GPL license, optional)

---

### Pandas Source

**Module**: `obsei.source.pandas_source`

**Purpose**: Read data from DataFrame

**Configuration**:
```python
import pandas as pd
from obsei.source.pandas_source import PandasSource, PandasSourceConfig

df = pd.read_csv("data.csv")

source_config = PandasSourceConfig(
    dataframe=df,
    text_columns=["title", "description"],         # Columns to combine
    include_columns=["rating", "date"]             # Include in metadata
)

source = PandasSource()
```

---

## Analyzers

### Zero-Shot Classification

**Module**: `obsei.analyzer.classification_analyzer`

**Purpose**: Classify text without training data

**Configuration**:
```python
from obsei.analyzer.classification_analyzer import (
    ZeroShotClassificationAnalyzer,
    ClassificationAnalyzerConfig
)

analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli",
    device="auto"                                  # auto|cpu|cuda:0
)

analyzer_config = ClassificationAnalyzerConfig(
    labels=["positive", "negative", "neutral"],
    multi_class_classification=True,               # Allow multiple labels
    label_map={                                    # Optional: rename labels
        "positive": "Satisfied",
        "negative": "Unsatisfied"
    }
)

results = analyzer.analyze_input(source_responses, analyzer_config)
```

**Recommended Models**:
- `typeform/mobilebert-uncased-mnli` (fast, mobile-optimized)
- `facebook/bart-large-mnli` (accurate, slower)
- `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (state-of-the-art)

---

### Sentiment Analysis (Vader)

**Module**: `obsei.analyzer.sentiment_analyzer`

**Purpose**: Dictionary-based sentiment analysis (no ML model needed)

**Configuration**:
```python
from obsei.analyzer.sentiment_analyzer import VaderSentimentAnalyzer

analyzer = VaderSentimentAnalyzer()
analyzer_config = None  # Vader doesn't need config

results = analyzer.analyze_input(source_responses, analyzer_config)
```

**Output**: Compound score from -1 (negative) to +1 (positive)

**Advantages**: Fast, no GPU needed, good for English social media text

---

### Named Entity Recognition (NER)

**Module**: `obsei.analyzer.ner_analyzer`

**Purpose**: Extract named entities (person, organization, location, etc.)

**Configuration**:
```python
from obsei.analyzer.ner_analyzer import NERAnalyzer

analyzer = NERAnalyzer(
    model_name_or_path="elastic/distilbert-base-cased-finetuned-conll03-english",
    device="auto"
)

analyzer_config = None  # No config needed

results = analyzer.analyze_input(source_responses, analyzer_config)
```

**Recommended Models**:
- `elastic/distilbert-base-cased-finetuned-conll03-english` (fast)
- `dslim/bert-base-NER` (accurate)
- `Jean-Baptiste/roberta-large-ner-english` (state-of-the-art)

**Entity Types**: PER, ORG, LOC, MISC (standard CoNLL-2003)

---

### Translation

**Module**: `obsei.analyzer.translation_analyzer`

**Purpose**: Translate text between languages

**Configuration**:
```python
from obsei.analyzer.translation_analyzer import TranslationAnalyzer

analyzer = TranslationAnalyzer(
    model_name_or_path="Helsinki-NLP/opus-mt-hi-en",  # Hindi to English
    device="auto"
)

analyzer_config = None

results = analyzer.analyze_input(source_responses, analyzer_config)
```

**Model Format**: `Helsinki-NLP/opus-mt-{src}-{tgt}`

**Popular Models**:
- `Helsinki-NLP/opus-mt-es-en` (Spanish → English)
- `Helsinki-NLP/opus-mt-fr-en` (French → English)
- `Helsinki-NLP/opus-mt-de-en` (German → English)
- `Helsinki-NLP/opus-mt-zh-en` (Chinese → English)

---

### PII Anonymizer

**Module**: `obsei.analyzer.pii_analyzer`

**Purpose**: Detect and anonymize personally identifiable information

**Configuration**:
```python
from obsei.analyzer.pii_analyzer import (
    PresidioPIIAnalyzer,
    PresidioPIIAnalyzerConfig,
    PresidioEngineConfig,
    PresidioModelConfig
)

analyzer = PresidioPIIAnalyzer(
    engine_config=PresidioEngineConfig(
        nlp_engine_name="spacy",
        models=[PresidioModelConfig(
            model_name="en_core_web_lg",
            lang_code="en"
        )]
    )
)

analyzer_config = PresidioPIIAnalyzerConfig(
    analyze_only=False,                            # False = anonymize
    return_decision_process=True
)

results = analyzer.analyze_input(source_responses, analyzer_config)
```

**Detects**: Email, phone, credit card, SSN, IP address, name, etc.

**Anonymization Methods**: Replace, redact, hash, encrypt

---

### Dummy Analyzer

**Module**: `obsei.analyzer.dummy_analyzer`

**Purpose**: Pass-through analyzer for testing

**Configuration**:
```python
from obsei.analyzer.dummy_analyzer import DummyAnalyzer, DummyAnalyzerConfig

analyzer = DummyAnalyzer()
analyzer_config = DummyAnalyzerConfig()

results = analyzer.analyze_input(source_responses, analyzer_config)
```

---

## Sinks (Informers)

### Slack Sink

**Module**: `obsei.sink.slack_sink`

**Purpose**: Send messages to Slack channels

**Configuration**:
```python
from obsei.sink.slack_sink import SlackSink, SlackSinkConfig

sink_config = SlackSinkConfig(
    slack_token="xoxb-your-token",
    channel_id="C01XXXXXX",                        # Channel ID (not name)
    message_template="New feedback: {processed_text}"  # Optional template
)

sink = SlackSink()
responses = sink.send_data(analyzer_responses, sink_config)
```

**Authentication**: Requires Slack Bot Token with `chat:write` scope

---

### Jira Sink

**Module**: `obsei.sink.jira_sink`

**Purpose**: Create Jira issues/tickets

**Configuration**:
```python
from obsei.sink.jira_sink import JiraSink, JiraSinkConfig

sink_config = JiraSinkConfig(
    url="https://your-domain.atlassian.net",
    username="user@example.com",
    password="<api_token>",                        # Jira API token
    issue_type={"name": "Task"},
    project={"key": "PROJ"},
    labels=["customer-feedback"],                   # Optional
    assignee={"name": "username"}                   # Optional
)

sink = JiraSink()
```

**Authentication**: Requires Jira API token

---

### Zendesk Sink

**Module**: `obsei.sink.zendesk_sink`

**Purpose**: Create Zendesk support tickets

**Configuration**:
```python
from obsei.sink.zendesk_sink import ZendeskSink, ZendeskSinkConfig, ZendeskCredInfo

sink_config = ZendeskSinkConfig(
    domain="zendesk.com",
    subdomain="your-company",
    cred_info=ZendeskCredInfo(
        email="admin@example.com",
        password="<password>"                      # Or API token
    ),
    ticket_type="question",                        # question|incident|problem|task
    priority="normal"                              # low|normal|high|urgent
)

sink = ZendeskSink()
```

---

### Elasticsearch Sink

**Module**: `obsei.sink.elasticsearch_sink`

**Purpose**: Index documents in Elasticsearch

**Configuration**:
```python
from obsei.sink.elasticsearch_sink import ElasticSearchSink, ElasticSearchSinkConfig

sink_config = ElasticSearchSinkConfig(
    hosts="http://localhost:9200",
    index_name="feedback",
    username="elastic",                            # Optional
    password="password"                            # Optional
)

sink = ElasticSearchSink()
```

---

### HTTP Sink

**Module**: `obsei.sink.http_sink`

**Purpose**: POST data to any HTTP endpoint

**Configuration**:
```python
from obsei.sink.http_sink import HttpSink, HttpSinkConfig

sink_config = HttpSinkConfig(
    url="https://api.example.com/webhook",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer <token>"
    },
    payload_template={                             # Optional custom format
        "text": "{processed_text}",
        "sentiment": "{segmented_data.sentiment}"
    }
)

sink = HttpSink()
```

---

### Pandas Sink

**Module**: `obsei.sink.pandas_sink`

**Purpose**: Store results in DataFrame

**Configuration**:
```python
from pandas import DataFrame
from obsei.sink.pandas_sink import PandasSink, PandasSinkConfig

sink_config = PandasSinkConfig(
    dataframe=DataFrame()
)

sink = PandasSink()
responses = sink.send_data(analyzer_responses, sink_config)

# Access the populated dataframe
df = sink_config.dataframe
df.to_csv("results.csv", index=False)
```

---

### Logger Sink

**Module**: `obsei.sink.logger_sink`

**Purpose**: Log to console/file (for testing)

**Configuration**:
```python
import logging
from obsei.sink.logger_sink import LoggerSink, LoggerSinkConfig

logger = logging.getLogger(__name__)

sink_config = LoggerSinkConfig(
    logger=logger,
    level=logging.INFO
)

sink = LoggerSink()
```

---

## Preprocessors

### Text Cleaner

**Module**: `obsei.preprocessor.text_cleaner`

**Purpose**: Clean and normalize text

**Configuration**:
```python
from obsei.preprocessor.text_cleaner import TextCleaner, TextCleanerConfig
from obsei.preprocessor.text_cleaning_function import (
    remove_url,
    remove_email,
    remove_html,
    to_lower_case
)

cleaner = TextCleaner()

config = TextCleanerConfig(
    cleaning_functions=[
        remove_url,
        remove_email,
        remove_html,
        to_lower_case
    ]
)

# Use in analyzer config
analyzer_config = ClassificationAnalyzerConfig(
    labels=["positive", "negative"],
    preprocessor=cleaner,
    preprocessor_config=config
)
```

**Available Functions**:
- `remove_url`: Remove URLs
- `remove_email`: Remove email addresses
- `remove_html`: Strip HTML tags
- `remove_emoji`: Remove emojis
- `remove_punctuation`: Remove punctuation
- `to_lower_case`: Convert to lowercase
- `to_upper_case`: Convert to uppercase
- `remove_extra_whitespace`: Normalize whitespace

---

### Text Splitter

**Module**: `obsei.preprocessor.text_splitter`

**Purpose**: Split long texts into chunks

**Configuration**:
```python
from obsei.preprocessor.text_splitter import TextSplitter, TextSplitterConfig

splitter = TextSplitter()

config = TextSplitterConfig(
    method="word",                                 # word|sentence|character
    max_length=500,                                # Max tokens/words per chunk
    overlap=50,                                    # Overlap between chunks
    separator=" "                                  # For character splitting
)

# Use in analyzer config
analyzer_config = ClassificationAnalyzerConfig(
    labels=["topic1", "topic2"],
    preprocessor=splitter,
    preprocessor_config=config
)
```

**Methods**:
- `word`: Split by word count
- `sentence`: Split by sentences
- `character`: Split by character count

---

## Postprocessors

### Inference Aggregator

**Module**: `obsei.postprocessor.inference_aggregator`

**Purpose**: Aggregate results from text chunks

**Configuration**:
```python
from obsei.postprocessor.inference_aggregator import InferenceAggregator, InferenceAggregatorConfig
from obsei.postprocessor.inference_aggregator_function import max_score, avg_score

aggregator = InferenceAggregator()

config = InferenceAggregatorConfig(
    aggregate_function=max_score                   # or avg_score
)

# Use in analyzer config
analyzer_config = ClassificationAnalyzerConfig(
    labels=["positive", "negative"],
    preprocessor=text_splitter,
    postprocessor=aggregator,
    postprocessor_config=config
)
```

**Aggregation Functions**:
- `max_score`: Use maximum score across chunks
- `avg_score`: Average scores across chunks
- Custom: Define your own aggregation function

---

## Utility Components

### Workflow Store

**Module**: `obsei.workflow.store`

**Purpose**: Persist workflow state

**Configuration**:
```python
from obsei.workflow.store import WorkflowStore
from sqlalchemy import create_engine

# SQLite
engine = create_engine('sqlite:///obsei_state.db')

# PostgreSQL
engine = create_engine('postgresql://user:pass@localhost/dbname')

# MySQL
engine = create_engine('mysql://user:pass@localhost/dbname')

store = WorkflowStore(engine=engine)

# Use in source config
source_config.state_store = store
```

---

## Configuration Patterns

### Environment Variables

```python
import os

# Best practice: use environment variables
source_config = TwitterSourceConfig(
    keywords=["feedback"],
    cred_info=TwitterCredentials(
        consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
        consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
        bearer_token=os.getenv("TWITTER_BEARER_TOKEN")
    )
)
```

### Configuration File

```python
import yaml
from obsei.configuration import ObseiConfiguration

with open("config.yaml") as f:
    config_dict = yaml.safe_load(f)

config = ObseiConfiguration.from_dict(config_dict)
```

---

## Common Combinations

### Social Listening → Sentiment → Alert

```python
# Source
twitter_source + TwitterConfig(keywords=["@brand"])

# Analyzer
vader_sentiment + None

# Sink (conditional)
if sentiment < -0.5:
    slack_sink + SlackConfig(channel="alerts")
```

### Review Monitoring → Classification → Ticket

```python
# Source
playstore_source + PlayStoreConfig(app_id="...")

# Analyzer
classification + Config(labels=["bug", "feature", "praise"])

# Sink (conditional)
if label == "bug":
    jira_sink + JiraConfig(issue_type="Bug")
```

### News Tracking → Translation → Storage

```python
# Source
google_news + NewsConfig(query="...", lang="es")

# Analyzer
translation + None  # Spanish to English

# Sink
elasticsearch_sink + ESConfig(index="news")
```

---

## Performance Tips

1. **Use smaller models for faster inference**:
   - `typeform/mobilebert-uncased-mnli` instead of `facebook/bart-large-mnli`

2. **Batch processing**:
   - Collect multiple items before analyzing

3. **GPU usage**:
   - Set `device="cuda:0"` for GPU acceleration

4. **Caching**:
   - Models are cached automatically after first load

5. **State management**:
   - Always use WorkflowStore to avoid re-processing

---

## Error Handling Examples

```python
try:
    source_responses = source.lookup(source_config)
except AuthenticationError:
    # Handle invalid credentials
    logger.error("Authentication failed")
except RateLimitError:
    # Handle rate limits
    time.sleep(60)
    source_responses = source.lookup(source_config)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

---

## Version Compatibility

| Component | Min Version | Tested Version |
|-----------|-------------|----------------|
| Python | 3.8 | 3.8-3.11 |
| PyTorch | 2.1.2 | 2.9.1 |
| Transformers | 4.36.2 | 4.57.1 |
| spaCy | 3.7.2 | 3.8.9 |
| SQLAlchemy | 2.0.24 | 2.0.44 |
| Pydantic | 2.5.3 | 2.12.4 |

---

**Last Updated**: November 16, 2025  
**Document Version**: 1.0
