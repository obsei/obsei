# Obsei Quick Start Guide

A practical guide to get started with Obsei in 15 minutes.

---

## Table of Contents

1. [Installation](#installation)
2. [First Workflow](#first-workflow)
3. [Common Patterns](#common-patterns)
4. [Best Practices](#best-practices)
5. [Troubleshooting](#troubleshooting)

---

## Installation

### Step 1: Install Python

Ensure you have Python 3.8 or higher:

```bash
python --version  # Should be 3.8+
```

### Step 2: Install Obsei

For trying out features:

```bash
pip install obsei[all]
```

For production (install only what you need):

```bash
# Example: Twitter source + classification + Slack sink
pip install obsei[twitter-api,analyzer,slack-api]
```

### Step 3: Download Required Models (if using analyzers)

```bash
# For text classification and NLP tasks
python -m spacy download en_core_web_sm
```

---

## First Workflow

Let's build a simple workflow: **Monitor Play Store reviews → Classify sentiment → Log results**

### Complete Example

```python
import logging
import sys
from obsei.source.playstore_scrapper import PlayStoreScrapperConfig, PlayStoreScrapperSource
from obsei.analyzer.sentiment_analyzer import VaderSentimentAnalyzer
from obsei.sink.logger_sink import LoggerSink, LoggerSinkConfig

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Step 1: Configure Source (Play Store Reviews)
source_config = PlayStoreScrapperConfig(
    app_url='https://play.google.com/store/apps/details?id=com.google.android.gm',
    max_count=5  # Fetch 5 recent reviews
)
source = PlayStoreScrapperSource()

# Step 2: Configure Analyzer (Sentiment Analysis)
analyzer = VaderSentimentAnalyzer()
analyzer_config = None  # Vader doesn't need config

# Step 3: Configure Sink (Console Logger)
sink_config = LoggerSinkConfig(
    logger=logger,
    level=logging.INFO
)
sink = LoggerSink()

# Step 4: Execute Workflow
print("Fetching reviews...")
source_responses = source.lookup(source_config)
print(f"Found {len(source_responses)} reviews")

print("Analyzing sentiment...")
analyzer_responses = analyzer.analyze_input(
    source_response_list=source_responses,
    analyzer_config=analyzer_config
)

print("Sending to logger...")
sink.send_data(analyzer_responses, sink_config)

print("Done!")
```

### Run the Example

```bash
python my_first_workflow.py
```

---

## Common Patterns

### Pattern 1: Social Media Monitoring with Slack Alerts

```python
from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig, TwitterCredentials
from obsei.analyzer.classification_analyzer import (
    ZeroShotClassificationAnalyzer,
    ClassificationAnalyzerConfig
)
from obsei.sink.slack_sink import SlackSink, SlackSinkConfig

# Configure Twitter source
source_config = TwitterSourceConfig(
    keywords=["#YourProduct", "@YourCompany"],
    lookup_period="1h",
    cred_info=TwitterCredentials(
        consumer_key="YOUR_KEY",
        consumer_secret="YOUR_SECRET",
        bearer_token="YOUR_TOKEN"
    )
)
source = TwitterSource()

# Configure classifier to detect complaints
analyzer_config = ClassificationAnalyzerConfig(
    labels=["complaint", "question", "praise", "bug report"]
)
analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli"
)

# Configure Slack sink
sink_config = SlackSinkConfig(
    slack_token="YOUR_SLACK_TOKEN",
    channel_id="YOUR_CHANNEL_ID"
)
sink = SlackSink()

# Execute workflow
source_responses = source.lookup(source_config)
analyzer_responses = analyzer.analyze_input(source_responses, analyzer_config)
sink.send_data(analyzer_responses, sink_config)
```

### Pattern 2: Multi-Source Analysis

```python
# Collect from multiple sources
sources = [
    (PlayStoreScrapperSource(), playstore_config),
    (AppStoreScrapperSource(), appstore_config),
    (TwitterSource(), twitter_config)
]

all_responses = []
for source, config in sources:
    responses = source.lookup(config)
    all_responses.extend(responses)

# Analyze all at once
analyzer_responses = analyzer.analyze_input(all_responses, analyzer_config)
```

### Pattern 3: Long Text Processing with Splitting

```python
from obsei.preprocessor.text_splitter import TextSplitter
from obsei.postprocessor.inference_aggregator import InferenceAggregator

# Split long texts into chunks
splitter = TextSplitter(
    method="word",
    max_length=500,
    overlap=50
)

# Aggregate results
aggregator = InferenceAggregator()

# In analyzer config
analyzer_config = ClassificationAnalyzerConfig(
    labels=["positive", "negative"],
    preprocessor=splitter,
    postprocessor=aggregator
)
```

### Pattern 4: State Management for Scheduled Jobs

```python
from obsei.workflow.store import WorkflowStore
from sqlalchemy import create_engine

# Create database for state storage
engine = create_engine('sqlite:///obsei_state.db')
store = WorkflowStore(engine=engine)

# Use in source config
source_config = TwitterSourceConfig(
    keywords=["feedback"],
    lookup_period="1h",
    cred_info=credentials,
    state_store=store
)

# First run: fetches all data from last hour
# Second run: only fetches new data since last run
```

---

## Best Practices

### 1. Environment Variables for Credentials

Never hardcode credentials:

```python
import os

credentials = TwitterCredentials(
    consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
    consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
    bearer_token=os.getenv("TWITTER_BEARER_TOKEN")
)
```

### 2. Error Handling

Wrap workflows in try-except:

```python
try:
    source_responses = source.lookup(source_config)
    analyzer_responses = analyzer.analyze_input(source_responses, analyzer_config)
    sink.send_data(analyzer_responses, sink_config)
except Exception as e:
    logger.error(f"Workflow failed: {e}")
    # Send alert or retry
```

### 3. Logging for Debugging

Use verbose logging during development:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log intermediate results
for idx, response in enumerate(source_responses):
    logger.debug(f"Response {idx}: {response.processed_text[:100]}")
```

### 4. Resource Management

For production, manage resources:

```python
# Use GPU efficiently
analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="model-name",
    device="cuda:0"  # Specify GPU
)

# Batch processing
batch_size = 10
for i in range(0, len(responses), batch_size):
    batch = responses[i:i+batch_size]
    analyzer.analyze_input(batch, config)
```

### 5. Rate Limiting

Respect API limits:

```python
import time

for keyword in keywords:
    source_config.keywords = [keyword]
    responses = source.lookup(source_config)
    # Process responses
    time.sleep(15)  # Wait 15s between requests
```

---

## Troubleshooting

### Issue 1: Model Download Fails

**Problem**: `ConnectionError` when loading model

**Solution**:
```bash
# Pre-download the model
python -c "from transformers import pipeline; pipeline('zero-shot-classification')"
```

### Issue 2: GPU Out of Memory

**Problem**: `CUDA out of memory`

**Solutions**:
```python
# 1. Use smaller model
analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli"  # Smaller
)

# 2. Use CPU instead
analyzer = ZeroShotClassificationAnalyzer(
    device="cpu"
)

# 3. Process in smaller batches
# Reduce max_count in source configs
```

### Issue 3: Import Errors

**Problem**: `ModuleNotFoundError: No module named 'X'`

**Solution**:
```bash
# Install the specific optional dependency
pip install obsei[twitter-api]  # For Twitter
pip install obsei[analyzer]     # For ML models
pip install obsei[all]          # For everything
```

### Issue 4: API Authentication Failed

**Problem**: `401 Unauthorized` or `403 Forbidden`

**Solutions**:
1. Check credentials are correct
2. Ensure API access is enabled in the platform
3. Verify token hasn't expired
4. Check API rate limits

### Issue 5: No Data Retrieved

**Problem**: Empty response list

**Solutions**:
```python
# 1. Check lookup_period
source_config.lookup_period = "24h"  # Extend period

# 2. Verify keywords/filters
source_config.keywords = ["broader", "terms"]

# 3. Check state store (might have already fetched)
# Clear state or use new store
```

---

## Example: Complete Production Workflow

```python
#!/usr/bin/env python3
"""
Production-ready Obsei workflow with error handling,
logging, and state management.
"""

import logging
import os
import sys
from datetime import datetime

from obsei.source.playstore_scrapper import PlayStoreScrapperConfig, PlayStoreScrapperSource
from obsei.analyzer.classification_analyzer import (
    ZeroShotClassificationAnalyzer,
    ClassificationAnalyzerConfig
)
from obsei.sink.slack_sink import SlackSink, SlackSinkConfig
from obsei.workflow.store import WorkflowStore
from sqlalchemy import create_engine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('obsei_workflow.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting Obsei workflow...")
        
        # State management
        engine = create_engine('sqlite:///obsei_state.db')
        store = WorkflowStore(engine=engine)
        
        # Configure source
        source_config = PlayStoreScrapperConfig(
            app_url=os.getenv("APP_URL"),
            max_count=50,
            state_store=store
        )
        source = PlayStoreScrapperSource()
        
        # Configure analyzer
        analyzer_config = ClassificationAnalyzerConfig(
            labels=["bug", "feature_request", "praise", "complaint"]
        )
        analyzer = ZeroShotClassificationAnalyzer(
            model_name_or_path="typeform/mobilebert-uncased-mnli",
            device="auto"
        )
        
        # Configure sink
        sink_config = SlackSinkConfig(
            slack_token=os.getenv("SLACK_TOKEN"),
            channel_id=os.getenv("SLACK_CHANNEL")
        )
        sink = SlackSink()
        
        # Execute workflow
        logger.info("Fetching data from source...")
        source_responses = source.lookup(source_config)
        logger.info(f"Retrieved {len(source_responses)} items")
        
        if not source_responses:
            logger.info("No new data to process")
            return
        
        logger.info("Analyzing data...")
        analyzer_responses = analyzer.analyze_input(
            source_responses,
            analyzer_config
        )
        
        logger.info("Sending to sink...")
        sink_responses = sink.send_data(analyzer_responses, sink_config)
        
        logger.info(f"Successfully processed {len(analyzer_responses)} items")
        logger.info("Workflow completed successfully")
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Run as Scheduled Job

```bash
# Add to crontab for hourly execution
# crontab -e
0 * * * * /usr/bin/python3 /path/to/workflow.py
```

---

## Next Steps

1. **Explore Examples**: Check the `example/` directory for more use cases
2. **Try Tutorials**: Run Jupyter notebooks in `tutorials/` directory
3. **Read Full Docs**: Visit https://obsei.com for comprehensive documentation
4. **Join Community**: GitHub Discussions, Slack workspace
5. **Contribute**: See CONTRIBUTING.md for guidelines

---

## Useful Commands Reference

```bash
# Installation
pip install obsei[all]                    # Full installation
pip install obsei[twitter-api,analyzer]  # Specific features

# Model downloads
python -m spacy download en_core_web_sm   # Small model
python -m spacy download en_core_web_lg   # Large model

# Testing
pytest                                    # Run tests
pytest -v                                 # Verbose
coverage run -m pytest                    # With coverage

# Code quality
black .                                   # Format code
mypy obsei                                # Type check
pre-commit run --all-files               # Run all checks

# Development
pip install -e .[dev,all]                # Editable install
```

---

## Support

- **Issues**: https://github.com/obsei/obsei/issues
- **Discussions**: https://github.com/obsei/obsei/discussions
- **Email**: contact@oraika.com

---

**Happy Automating! 🚀**
