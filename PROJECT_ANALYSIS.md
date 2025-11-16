# Obsei Project Analysis

## Executive Summary

**Obsei** (pronounced "Ob see" | /əb-'sē/) is an open-source, low-code, AI-powered automation tool designed to streamline the collection, analysis, and distribution of unstructured data from various sources. The project is currently in **alpha stage** and should be used carefully in production environments.

**Version**: 0.0.15  
**License**: Apache 2.0  
**Python Support**: 3.8, 3.9, 3.10, 3.11  
**Maintainers**: [Oraika Technologies](https://www.oraika.com) - Lalit Pagaria and Girish Patel

---

## Project Overview

### Core Purpose

Obsei is designed to automate cognitive workflows by connecting three key components:

1. **Observer (Source)**: Collect unstructured data from various channels
2. **Analyzer**: Process data using AI/ML models for insights
3. **Informer (Sink)**: Send processed data to destination platforms

### Key Use Cases

- **Social Listening**: Monitor social media posts, comments, and customer feedback
- **Alerting/Notification**: Automatic alerts for customer complaints, qualified sales leads
- **Customer Support Automation**: Auto-create tickets from social media complaints
- **Content Classification**: Auto-assign tags based on content analysis
- **Market Research**: Extract insights from various feedback platforms
- **Dataset Creation**: Generate training data for AI tasks

---

## Architecture

### High-Level Design

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Observer  │ ───> │   Analyzer   │ ───> │  Informer   │
│  (Source)   │      │              │      │   (Sink)    │
└─────────────┘      └──────────────┘      └─────────────┘
      │                                            │
      ▼                                            ▼
┌─────────────┐                          ┌─────────────┐
│   State     │                          │ Destination │
│  Storage    │                          │  Platform   │
│ (Database)  │                          │             │
└─────────────┘                          └─────────────┘
```

### Directory Structure

```
obsei/
├── __init__.py              # Package initialization
├── _version.py              # Version management
├── configuration.py         # Configuration utilities
├── payload.py              # Data payload models
├── processor.py            # Base processor classes
├── process_workflow.py     # Workflow orchestration
│
├── source/                 # Observer/Source components
│   ├── twitter_source.py
│   ├── reddit_source.py
│   ├── playstore_scrapper.py
│   ├── appstore_scrapper.py
│   ├── facebook_source.py
│   ├── email_source.py
│   ├── google_news_source.py
│   ├── youtube_scrapper.py
│   ├── website_crawler_source.py
│   └── pandas_source.py
│
├── analyzer/              # Analysis components
│   ├── base_analyzer.py
│   ├── classification_analyzer.py
│   ├── sentiment_analyzer.py
│   ├── ner_analyzer.py
│   ├── translation_analyzer.py
│   ├── pii_analyzer.py
│   └── dummy_analyzer.py
│
├── sink/                  # Informer/Sink components
│   ├── slack_sink.py
│   ├── jira_sink.py
│   ├── zendesk_sink.py
│   ├── elasticsearch_sink.py
│   ├── http_sink.py
│   ├── pandas_sink.py
│   └── logger_sink.py
│
├── preprocessor/          # Text preprocessing
│   ├── text_cleaner.py
│   ├── text_splitter.py
│   └── text_tokenizer.py
│
├── postprocessor/         # Post-analysis processing
│   └── inference_aggregator.py
│
├── workflow/              # Workflow management
│   ├── workflow.py
│   └── store.py
│
└── misc/                  # Utilities
    └── utils.py
```

---

## Core Components

### 1. Sources (Observers)

Sources collect unstructured data from various platforms:

#### Social Media
- **Twitter**: Fetch tweets by keywords, hashtags, or users
- **Reddit**: Retrieve posts and comments from subreddits (API & Scraper)
- **Facebook**: Get page posts and comments
- **YouTube**: Scrape video comments and replies

#### Review Platforms
- **Google Play Store**: App reviews (API & Scraper)
- **Apple App Store**: App reviews scraper
- **Google Maps**: Location reviews scraper

#### News & Web
- **Google News**: News articles by query
- **Web Crawler**: Extract text from websites

#### Communication
- **Email**: IMAP email monitoring
- **Pandas DataFrame**: CSV/TSV data sources

**Key Features**:
- State management (store last fetch position)
- Configurable lookup periods (e.g., "1h", "2d", "3M")
- Support for multiple databases (SQLite, PostgreSQL, MySQL)

### 2. Analyzers

Analyzers process text using AI/ML models:

#### Classification Analyzers
- **Zero-Shot Classification**: Classify without training data
- **Text Classification**: Multi-label classification
- Supports HuggingFace transformer models

#### Sentiment Analysis
- **Vader Sentiment**: Dictionary-based, lightweight
- **Transformer-based**: Deep learning sentiment models

#### Named Entity Recognition (NER)
- Extract entities (person, organization, location, etc.)
- Supports custom NER models from HuggingFace

#### Other Analyzers
- **Translation**: Multi-language translation
- **PII Anonymizer**: Detect and anonymize personal information
- **Dummy Analyzer**: Pass-through for testing

**Device Support**: 
- `auto`: Use GPU if available, else CPU
- `cpu`: Force CPU usage
- `cuda:0`: Use specific GPU

### 3. Sinks (Informers)

Sinks send processed data to destinations:

#### Ticketing & Collaboration
- **Jira**: Create issues/tickets
- **Zendesk**: Create support tickets
- **Slack**: Send notifications to channels

#### Data Storage
- **Elasticsearch**: Index documents
- **Pandas DataFrame**: Store in DataFrames
- **HTTP**: POST to custom endpoints

#### Testing
- **Logger Sink**: Console/file logging for debugging

### 4. Preprocessors

Text preprocessing utilities:

- **Text Cleaner**: Remove noise, normalize text
- **Text Splitter**: Split long texts into chunks
- **Text Tokenizer**: Tokenize text for analysis

### 5. Postprocessors

Post-analysis processing:

- **Inference Aggregator**: Combine results from multiple chunks
- Support for custom aggregation functions

---

## Workflow Pattern

### Basic Workflow

```python
# 1. Configure Source
source_config = TwitterSourceConfig(
    keywords=["customer feedback"],
    lookup_period="1h",
    cred_info=TwitterCredentials(...)
)
source = TwitterSource()

# 2. Configure Analyzer
analyzer_config = ClassificationAnalyzerConfig(
    labels=["positive", "negative", "neutral"]
)
analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli"
)

# 3. Configure Sink
sink_config = SlackSinkConfig(
    slack_token="<token>",
    channel_id="<channel>"
)
sink = SlackSink()

# 4. Execute Workflow
source_response_list = source.lookup(source_config)
analyzer_response_list = analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config
)
sink_response_list = sink.send_data(analyzer_response_list, sink_config)
```

### Advanced Workflow with State Management

```python
from obsei.workflow.store import WorkflowStore

# Create state store
store = WorkflowStore(state_persistence_config)

# Use store in source config
source_config = TwitterSourceConfig(
    keywords=["feedback"],
    lookup_period="1h",
    cred_info=credentials,
    state_store=store
)

# Subsequent runs will fetch only new data
```

---

## Installation & Dependencies

### Installation Options

```bash
# Core only
pip install obsei

# All features
pip install obsei[all]

# Specific features
pip install obsei[twitter-api,analyzer,slack-api]
```

### Dependency Groups

- **source**: All observer dependencies
- **sink**: All informer dependencies
- **analyzer**: ML/AI model dependencies (PyTorch, Transformers, etc.)
- **dev**: Development tools (pytest, mypy, black, pre-commit)
- **all**: Everything combined

### Core Dependencies

- **pydantic >= 2.5.3**: Data validation
- **SQLAlchemy >= 2.0.24**: Database ORM
- **beautifulsoup4**: HTML parsing
- **requests**: HTTP client
- **dateparser**: Date parsing

### Analyzer Dependencies

- **torch >= 2.1.2**: Deep learning framework
- **transformers >= 4.36.2**: HuggingFace models
- **spacy >= 3.7.2**: NLP toolkit
- **presidio-analyzer/anonymizer**: PII detection

---

## Testing & Quality

### Test Structure

```
test/
├── conftest.py                    # Pytest fixtures
├── test_analyzer.py               # Analyzer tests
├── test_imports.py                # Import validation
├── test_inference_aggregator.py   # Aggregation tests
├── test_pii_analyzer.py           # PII detection tests
├── test_text_cleaner.py           # Text cleaning tests
├── test_text_splitter.py          # Text splitting tests
└── test_translator.py             # Translation tests
```

### CI/CD Pipeline

GitHub Actions workflow:
1. **Type Check**: MyPy static type checking
2. **Build & Test**: 
   - Multi-OS (Ubuntu, macOS, Windows)
   - Multi-Python (3.8, 3.9, 3.10, 3.11)
   - Coverage reporting

### Code Quality Tools

- **Black**: Code formatting
- **MyPy**: Static type checking
- **Pre-commit**: Git hooks for quality checks
- **Coverage**: Test coverage reporting

---

## Configuration Management

### Configuration Files

- **pyproject.toml**: Project metadata, dependencies, build config
- **.pre-commit-config.yaml**: Pre-commit hooks
- **mypy.ini**: Type checker configuration

### Example Configuration

```python
from obsei.configuration import ObseiConfiguration

config = ObseiConfiguration(
    source_config=source_config,
    analyzer_config=analyzer_config,
    sink_config=sink_config
)
```

---

## Data Models

### TextPayload

Core data structure for text processing:

```python
class TextPayload(BasePayload):
    processed_text: str           # The text content
    segmented_data: Dict[str, Any]  # Analysis results
    meta: Dict[str, Any]           # Metadata
    source_name: Optional[str]     # Source identifier
```

### Workflow Response Types

- **SourceResponse**: Raw data from sources
- **AnalyzerResponse**: Analyzed data with insights
- **SinkResponse**: Confirmation from sinks

---

## Security Considerations

### PII Handling

Built-in PII anonymizer using Microsoft Presidio:
- Detects: Names, emails, phone numbers, SSN, credit cards
- Configurable recognition patterns
- Multi-language support via spaCy

### API Credentials

Credentials managed through configuration objects:
- Separate credential classes per source
- Environment variable support
- No hardcoded credentials in examples

### Third-Party Licenses

- Apache 2.0 (main license)
- Secondary permissive licenses (MIT, BSD, LGPL)
- Avoids strong copyleft (GPL, AGPL) for commercial friendliness

---

## Performance Considerations

### Model Loading

- Models downloaded from HuggingFace on first use
- Cached locally for subsequent runs
- Support for offline mode

### GPU Acceleration

- Automatic GPU detection and usage
- Configurable device selection
- Batch processing support

### Rate Limiting

- Built-in state management to avoid re-fetching
- Configurable lookup periods
- Respect API rate limits of sources

---

## Examples & Tutorials

### Example Scripts

Located in `example/` directory:
- `playstore_scrapper_example.py`: Play Store review analysis
- `twitter_source_example.py`: Twitter monitoring
- `slack_example.py`: Slack notifications
- `jira_example.py`: Jira ticket creation
- `pii_analyzer_example.py`: PII detection
- And more...

### Jupyter Tutorials

Located in `tutorials/` directory:
1. PlayStore → Classification → Logger
2. PlayStore → PreProcessing → Classification → Pandas
3. AppStore → PreProcessing → Classification → Pandas
4. Google News → Text Processing → Classification

Available on:
- Google Colab (interactive)
- Binder (cloud Jupyter)

---

## Development Workflow

### Contributing

1. Fork the repository
2. Create feature branch
3. Follow Google Python Style Guide
4. Add tests for new features
5. Run pre-commit hooks
6. Submit pull request

### Running Tests

```bash
# Install dev dependencies
pip install '.[dev,all]'

# Download spaCy models
python -m spacy download en_core_web_lg
python -m spacy download en_core_web_sm

# Run tests
pytest

# With coverage
coverage run -m pytest
coverage report -m

# Type checking
mypy obsei

# Format code
black .
```

---

## Known Limitations

1. **Alpha Stage**: Not production-ready, breaking changes expected
2. **Test Coverage**: Low coverage due to difficulty testing 3rd party APIs
3. **Conda Support**: Not available, PIP only
4. **GPU Memory**: Large models require significant VRAM
5. **Rate Limits**: External APIs have rate limits

---

## Roadmap & Future Direction

### Planned Features

- Multi-modal support (text, image, audio, video, documents)
- More data sources (private and public channels)
- Additional AI workflows for downstream automation
- Improved state management
- Better error handling and retry mechanisms

---

## Community & Support

### Resources

- **Documentation**: https://obsei.com
- **GitHub**: https://github.com/obsei/obsei
- **Discussions**: GitHub Discussions forum
- **Demo**: HuggingFace Spaces
- **Slack**: Community workspace
- **YouTube**: Tutorial videos

### Companies Using Obsei

- Oraika (contextual customer feedback)
- 1Page (meeting context)
- Spacepulse (space operations)
- Superblog (content platform)
- Zolve (financial services)
- Utilize (no-code app builder)

---

## Technical Stack Summary

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.8+ |
| **ML Frameworks** | PyTorch, Transformers, spaCy |
| **Data** | SQLAlchemy, Pandas |
| **Web** | Requests, BeautifulSoup |
| **Testing** | Pytest, Coverage |
| **Code Quality** | Black, MyPy, Pre-commit |
| **Build** | Hatchling (PEP 517) |
| **CI/CD** | GitHub Actions |

---

## Conclusion

Obsei is a powerful and flexible automation framework for text analysis workflows. Its modular architecture allows easy combination of different sources, analyzers, and sinks to build custom pipelines. While still in alpha, it demonstrates significant potential for automating cognitive tasks in customer feedback analysis, social listening, and content monitoring.

### Strengths

✅ Modular, extensible architecture  
✅ Wide range of pre-built integrations  
✅ State management for incremental processing  
✅ GPU acceleration support  
✅ Active development and community  
✅ Commercial-friendly licensing  

### Areas for Improvement

⚠️ Test coverage needs improvement  
⚠️ Documentation could be more comprehensive  
⚠️ Error handling and retry logic  
⚠️ Production readiness  
⚠️ More example workflows  

---

**Last Updated**: November 16, 2025  
**Analyzer**: GitHub Copilot  
**Analysis Version**: 1.0
