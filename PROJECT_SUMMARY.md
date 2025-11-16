# Obsei Project Summary

## What is Obsei?

**Obsei** is an open-source, low-code AI automation framework that connects data sources to AI analyzers and delivers insights to your preferred platforms. Think of it as a Swiss Army knife for text analysis workflows.

```
┌────────────┐      ┌──────────┐      ┌────────────┐
│  Collect   │  →   │ Analyze  │  →   │  Deliver   │
│   Data     │      │ with AI  │      │  Insights  │
└────────────┘      └──────────┘      └────────────┘
```

---

## Why Use Obsei?

### ✅ Strengths

1. **No Code Required**: Configure workflows with Python classes, no ML expertise needed
2. **Modular Design**: Mix and match 30+ components (sources, analyzers, sinks)
3. **State Management**: Automatically tracks what's been processed
4. **GPU Support**: Accelerate AI models with GPU when available
5. **Multiple Integrations**: Connect to popular platforms out-of-the-box
6. **Open Source**: Free to use, Apache 2.0 license

### ⚠️ Considerations

1. **Alpha Stage**: Still evolving, expect breaking changes
2. **Test Coverage**: Limited tests, especially for external APIs
3. **Documentation**: Improving but could be more comprehensive
4. **Production Ready**: Use cautiously, not battle-tested at scale

---

## Core Components

### 15+ Data Sources (Observers)

**Social Media**:
- Twitter (API v2)
- Reddit (API + Scraper)
- Facebook (Pages)
- YouTube (Comments)

**App Stores**:
- Google Play Store (API + Scraper)
- Apple App Store (Scraper)

**News & Web**:
- Google News
- Web Crawler
- RSS Feeds

**Communication**:
- Email (IMAP)
- Pandas DataFrames

**Reviews**:
- Google Maps Reviews

### 7+ AI Analyzers

**Text Classification**:
- Zero-shot classification (no training needed)
- Multi-label support
- Custom categories

**Sentiment Analysis**:
- Vader (dictionary-based, fast)
- Transformer models (deep learning)

**Other Analyzers**:
- Named Entity Recognition (NER)
- Translation (100+ language pairs)
- PII Anonymization
- Custom analyzers

### 7+ Delivery Destinations (Informers)

**Ticketing & Collaboration**:
- Jira (issue creation)
- Zendesk (support tickets)
- Slack (notifications)

**Data Storage**:
- Elasticsearch (indexing)
- Pandas DataFrames
- HTTP Webhooks

**Testing**:
- Console Logger

---

## How It Works

### Basic Workflow

```python
# 1. Configure where to get data
source_config = PlayStoreScrapperConfig(
    app_id="com.myapp",
    max_count=50
)
source = PlayStoreScrapperSource()

# 2. Configure how to analyze it
analyzer_config = ClassificationAnalyzerConfig(
    labels=["bug", "feature_request", "praise"]
)
analyzer = ZeroShotClassificationAnalyzer()

# 3. Configure where to send results
sink_config = SlackSinkConfig(
    channel_id="C123456"
)
sink = SlackSink()

# 4. Execute
data = source.lookup(source_config)
results = analyzer.analyze_input(data, analyzer_config)
sink.send_data(results, sink_config)
```

### Advanced Features

**State Management**: Tracks processed items in database
```python
store = WorkflowStore(engine=create_engine('sqlite:///state.db'))
source_config.state_store = store
# Now fetches only new items
```

**Text Preprocessing**: Clean and split long texts
```python
cleaner = TextCleaner(remove_urls=True, lowercase=True)
splitter = TextSplitter(max_length=500, overlap=50)
analyzer_config.preprocessor = cleaner
```

**Result Aggregation**: Combine results from chunks
```python
aggregator = InferenceAggregator(aggregate_function=max_score)
analyzer_config.postprocessor = aggregator
```

---

## Real-World Use Cases

### 1. Social Listening Dashboard

**Goal**: Monitor brand mentions across social media

```
Twitter + Reddit → Sentiment Analysis → Elasticsearch
                                      → Slack (if negative)
```

**Business Value**: Real-time brand health monitoring

### 2. App Review Triage

**Goal**: Automatically create tickets for bug reports

```
Play Store + App Store → Classification → Jira (if bug)
                       → Sentiment       → Slack (if negative)
```

**Business Value**: Faster response to critical issues

### 3. Customer Support Automation

**Goal**: Route customer emails to right team

```
Email → PII Anonymization → Classification → Zendesk
                                           → Assign to team
```

**Business Value**: Reduced manual email sorting

### 4. Market Intelligence

**Goal**: Track competitor mentions in news

```
Google News → Translation → NER → Elasticsearch
                                → Dashboard
```

**Business Value**: Competitive insights

### 5. Multi-Source Feedback Analysis

**Goal**: Aggregate feedback from all channels

```
Twitter + Reddit + Play Store + App Store → Classification → Pandas
                                          → Sentiment     → CSV Report
```

**Business Value**: Unified feedback view

---

## Technical Architecture

### High-Level

```
┌─────────────────────────────────────────────┐
│           Obsei Application                  │
├─────────────────────────────────────────────┤
│                                              │
│  Sources → [Preprocessor] → Analyzers →     │
│           [Postprocessor] → Sinks           │
│                                              │
│              ↕ State Store ↕                 │
│                                              │
└─────────────────────────────────────────────┘
```

### Technology Stack

- **Language**: Python 3.8+
- **ML Frameworks**: PyTorch, Transformers, spaCy
- **Database**: SQLAlchemy (SQLite, PostgreSQL, MySQL)
- **Data**: Pandas, NumPy
- **APIs**: Requests, various client SDKs
- **Build**: Hatchling (PEP 517)
- **Testing**: Pytest, Coverage
- **Quality**: Black, MyPy, Pre-commit

### Deployment Options

1. **Scheduled Jobs** (Cron)
   - Simple, reliable
   - Good for periodic checks

2. **Serverless** (AWS Lambda, Azure Functions)
   - Auto-scaling
   - Pay per execution

3. **Long-Running Service** (systemd)
   - Real-time processing
   - Always available

4. **Container** (Docker)
   - Portable
   - Easy deployment

---

## Performance Characteristics

### Speed

| Component | Performance |
|-----------|------------|
| Sources | API-limited (varies by platform) |
| Analyzers | CPU: 1-10 items/sec, GPU: 10-100 items/sec |
| Sinks | API-limited (varies by platform) |

### Resource Usage

| Component | CPU | Memory | GPU |
|-----------|-----|--------|-----|
| Sources | Low | Low | N/A |
| Vader Sentiment | Low | Low | N/A |
| Classification (CPU) | High | Medium | N/A |
| Classification (GPU) | Low | Low | High |
| NER | Medium | Medium | Optional |
| Sinks | Low | Low | N/A |

### Scalability

- **Vertical**: Use GPU for faster inference
- **Horizontal**: Run multiple instances with shared state store
- **Optimization**: Batch processing, model caching, smaller models

---

## Security & Privacy

### Authentication
- Credentials stored separately (env vars recommended)
- Support for API tokens, OAuth, basic auth
- No credentials in code examples

### PII Protection
- Built-in PII anonymizer (Microsoft Presidio)
- Detects: names, emails, phone, SSN, credit cards
- Methods: redact, replace, hash, encrypt

### Network
- HTTPS for all API calls
- No telemetry or tracking
- Local state storage

### Dependencies
- Regular security updates via Dependabot
- Avoids GPL licenses for commercial friendliness
- Transparent third-party attribution

---

## Installation & Setup

### Quick Install

```bash
# Full installation
pip install obsei[all]

# Specific features only
pip install obsei[twitter-api,analyzer,slack-api]
```

### Requirements

- Python 3.8+
- pip
- (Optional) CUDA for GPU acceleration
- (Optional) spaCy models for NLP

### First Run

```bash
# Install
pip install obsei[all]

# Download spaCy model (if using NLP)
python -m spacy download en_core_web_sm

# Run example
python -c "
from obsei.source.playstore_scrapper import *
from obsei.analyzer.sentiment_analyzer import *
from obsei.sink.logger_sink import *
import logging

logging.basicConfig(level=logging.INFO)

source = PlayStoreScrapperSource()
analyzer = VaderSentimentAnalyzer()
sink = LoggerSink()

data = source.lookup(PlayStoreScrapperConfig(
    app_url='https://play.google.com/store/apps/details?id=com.google.android.gm',
    max_count=5
))

results = analyzer.analyze_input(data, None)
sink.send_data(results, LoggerSinkConfig(
    logger=logging.getLogger('obsei')
))
"
```

---

## Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| **README.md** | Quick overview | Everyone |
| **PROJECT_SUMMARY.md** (this) | High-level summary | Decision makers |
| **QUICK_START_GUIDE.md** | Hands-on tutorial | New users |
| **PROJECT_ANALYSIS.md** | Detailed analysis | Technical evaluators |
| **ARCHITECTURE.md** | Technical deep dive | Architects, developers |
| **COMPONENT_REFERENCE.md** | API reference | Implementers |
| **DOCUMENTATION_INDEX.md** | Navigation guide | All users |

---

## Community & Support

### Getting Help

- **Questions**: [GitHub Discussions](https://github.com/obsei/obsei/discussions)
- **Bugs**: [GitHub Issues](https://github.com/obsei/obsei/issues)
- **Chat**: [Slack Community](https://join.slack.com/t/obsei-community/shared_invite/...)
- **Email**: contact@oraika.com

### Learning Resources

- **Examples**: `example/` directory (20+ scripts)
- **Tutorials**: `tutorials/` directory (Jupyter notebooks)
- **Videos**: [YouTube Channel](https://www.youtube.com/channel/UCqdvgro1BzU13tkAfX3jCJA)
- **Demo**: [HuggingFace Space](https://huggingface.co/spaces/obsei/obsei-demo)

### Contributing

- Read [CONTRIBUTING.md](CONTRIBUTING.md)
- Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Sign [Contributor License Agreement](CONTRIBUTOR_LICENSE_AGREEMENT.md)

---

## Companies Using Obsei

- **Oraika** - Customer feedback understanding
- **1Page** - Meeting context
- **Spacepulse** - Space operations
- **Superblog** - Content platform
- **Zolve** - Financial services
- **Utilize** - No-code apps

---

## Project Status

### Current State (v0.0.15)

- ✅ Core functionality complete
- ✅ 30+ components available
- ✅ Multi-platform support
- ⚠️ Alpha stage, evolving
- ⚠️ Limited test coverage
- ⚠️ Breaking changes possible

### Roadmap

1. **Near Term**
   - Improved error handling
   - Better documentation
   - More examples
   - Higher test coverage

2. **Medium Term**
   - Multi-modal support (images, audio)
   - More integrations
   - Performance optimizations
   - Production hardening

3. **Long Term**
   - Visual workflow builder
   - Cloud service offering
   - Enterprise features
   - Stable 1.0 release

---

## Comparison with Alternatives

### vs. Custom Scripts
- ✅ Faster development
- ✅ Battle-tested components
- ✅ State management included
- ❌ Less flexible

### vs. Enterprise Tools (Sprinklr, Brandwatch)
- ✅ Open source, free
- ✅ Fully customizable
- ✅ Self-hosted
- ❌ Less polished
- ❌ Requires technical skills

### vs. Zapier/IFTTT
- ✅ More AI capabilities
- ✅ Better for complex logic
- ✅ Self-hosted
- ❌ Requires coding
- ❌ No GUI

---

## Key Metrics

### Project
- **Stars**: 700+ on GitHub
- **Downloads**: Growing monthly
- **Contributors**: Active community
- **Age**: 2+ years in development
- **Updates**: Regular releases

### Code
- **Lines**: ~10,000+ Python
- **Components**: 30+
- **Tests**: 45+
- **Dependencies**: Well-maintained

---

## Decision Criteria

### Use Obsei If:

✅ You need AI-powered text analysis  
✅ You want to connect multiple data sources  
✅ You're comfortable with Python  
✅ You need customizable workflows  
✅ You prefer open source  
✅ You can tolerate alpha-stage software  

### Consider Alternatives If:

❌ You need GUI-only solution  
❌ You require enterprise support  
❌ You can't risk breaking changes  
❌ You need multi-modal (video, images)  
❌ You want zero-code solution  

---

## Quick Evaluation Checklist

- [ ] Review [README.md](README.md) for basic understanding
- [ ] Check [requirements](#requirements) match your environment
- [ ] Review [use cases](#real-world-use-cases) for relevance
- [ ] Examine [components](#core-components) for needed integrations
- [ ] Consider [limitations](#-considerations) for your scenario
- [ ] Try [first run](#first-run) to test functionality
- [ ] Explore [examples](example/) for similar use cases
- [ ] Assess [community](#community--support) activity
- [ ] Decide based on [criteria](#decision-criteria)

---

## Getting Started Path

### For Decision Makers (15 min)
1. Read this summary
2. Check use cases section
3. Review comparison with alternatives
4. Make go/no-go decision

### For Evaluators (1 hour)
1. Read PROJECT_ANALYSIS.md
2. Try Quick Start Guide
3. Review architecture
4. Assess fit for requirements

### For Implementers (4 hours)
1. Follow Quick Start Guide
2. Build first workflow
3. Study Component Reference
4. Explore examples directory
5. Review Architecture doc

### For Contributors (1 day)
1. All of the above
2. Read CONTRIBUTING.md
3. Set up dev environment
4. Run test suite
5. Find issue to work on

---

## Final Thoughts

Obsei is a **promising** open-source framework for building text analysis workflows. While still in alpha, it offers a solid foundation with:

- **Good**: Modular design, multiple integrations, active development
- **Great**: Open source, AI-powered, state management
- **Needs Work**: Documentation, test coverage, production readiness

**Best For**: Tech-savvy teams building custom text analysis pipelines who value flexibility over polish.

**Not Ideal For**: Non-technical users or mission-critical production systems requiring stability guarantees.

---

## Next Steps

1. **Try It**: Follow the [Quick Start Guide](QUICK_START_GUIDE.md)
2. **Learn More**: Read the [Project Analysis](PROJECT_ANALYSIS.md)
3. **Build Something**: Use the [Component Reference](COMPONENT_REFERENCE.md)
4. **Get Help**: Join the [Community](#community--support)
5. **Contribute**: Check [CONTRIBUTING.md](CONTRIBUTING.md)

---

**Project Homepage**: https://github.com/obsei/obsei  
**Documentation**: https://obsei.com  
**License**: Apache 2.0  
**Maintained By**: [Oraika Technologies](https://www.oraika.com)

---

*Last Updated: November 16, 2025*  
*Document Version: 1.0*  
*Obsei Version: 0.0.15*
