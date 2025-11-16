# Obsei Architecture Documentation

## Overview

This document provides a detailed technical architecture overview of the Obsei project, including component interactions, data flow, and design patterns.

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Obsei Platform                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐  │
│  │              │        │              │        │              │  │
│  │  Observers   │───────▶│  Analyzers   │───────▶│  Informers   │  │
│  │  (Sources)   │        │              │        │   (Sinks)    │  │
│  │              │        │              │        │              │  │
│  └──────┬───────┘        └──────┬───────┘        └──────┬───────┘  │
│         │                       │                       │           │
│         │                       │                       │           │
│         ▼                       ▼                       ▼           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │           Workflow Orchestration & State Management          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
    ┌───────────┐         ┌────────────┐        ┌─────────────┐
    │  External │         │  ML Models │        │ Destination │
    │   APIs    │         │   (Local/  │        │  Platforms  │
    │           │         │   Remote)  │        │             │
    └───────────┘         └────────────┘        └─────────────┘
```

---

## Component Architecture

### 1. Observer (Source) Component

```
┌─────────────────────────────────────────────────────────┐
│                    Source Component                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐                                     │
│  │ BaseSource      │  Abstract base class                │
│  │ (Interface)     │                                     │
│  └────────┬────────┘                                     │
│           │                                               │
│           │ Implements                                    │
│           │                                               │
│  ┌────────▼──────────────────────────────────────────┐  │
│  │  Concrete Source Implementations                  │  │
│  │  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │ TwitterSource│  │ RedditSource │ ...          │  │
│  │  └──────────────┘  └──────────────┘              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────┐               │
│  │  State Management                     │               │
│  │  - WorkflowStore (DB persistence)     │               │
│  │  - Last fetch timestamp                │               │
│  │  - Cursor/pagination info             │               │
│  └───────────────────────────────────────┘               │
│                                                           │
│  ┌───────────────────────────────────────┐               │
│  │  Configuration                         │               │
│  │  - Credentials                         │               │
│  │  - Query parameters                    │               │
│  │  - Lookup period                       │               │
│  └───────────────────────────────────────┘               │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

#### Source Interface

```python
class BaseSource:
    def lookup(self, config: SourceConfig) -> List[TextPayload]:
        """
        Fetch data from source
        
        Returns:
            List of TextPayload objects
        """
        pass
```

#### Key Responsibilities

- **Data Collection**: Fetch unstructured data from external platforms
- **Authentication**: Manage API credentials and tokens
- **Rate Limiting**: Respect platform rate limits
- **State Persistence**: Track what has been fetched to avoid duplicates
- **Data Normalization**: Convert platform-specific format to TextPayload

---

### 2. Analyzer Component

```
┌─────────────────────────────────────────────────────────────┐
│                    Analyzer Component                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐                                         │
│  │ BaseAnalyzer    │  Abstract base class                    │
│  │ (Interface)     │                                         │
│  └────────┬────────┘                                         │
│           │                                                   │
│           │ Implements                                        │
│           │                                                   │
│  ┌────────▼────────────────────────────────────────────┐    │
│  │  Analyzer Types                                     │    │
│  │  ┌─────────────────┐  ┌─────────────────┐         │    │
│  │  │ Classification  │  │   Sentiment     │         │    │
│  │  │   Analyzer      │  │   Analyzer      │  ...    │    │
│  │  └─────────────────┘  └─────────────────┘         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌───────────────────────────────────────────────┐           │
│  │  Preprocessing Pipeline                       │           │
│  │  - Text Cleaning                              │           │
│  │  - Text Splitting                             │           │
│  │  - Tokenization                               │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
│  ┌───────────────────────────────────────────────┐           │
│  │  Model Management                             │           │
│  │  - Model loading (HuggingFace)                │           │
│  │  - Device selection (CPU/GPU)                 │           │
│  │  - Caching                                    │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
│  ┌───────────────────────────────────────────────┐           │
│  │  Postprocessing Pipeline                      │           │
│  │  - Inference aggregation                      │           │
│  │  - Score normalization                        │           │
│  │  - Result formatting                          │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

#### Analyzer Interface

```python
class BaseAnalyzer:
    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: AnalyzerConfig
    ) -> List[TextPayload]:
        """
        Analyze text data
        
        Returns:
            List of TextPayload with segmented_data populated
        """
        pass
```

#### Processing Pipeline

```
Input TextPayload
       │
       ▼
┌──────────────┐
│ Preprocessor │ (Optional: Cleaning, Splitting)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   ML Model   │ (Classification, NER, Sentiment, etc.)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Postprocessor│ (Optional: Aggregation, Normalization)
└──────┬───────┘
       │
       ▼
Output TextPayload
(with segmented_data)
```

---

### 3. Informer (Sink) Component

```
┌─────────────────────────────────────────────────────────┐
│                    Sink Component                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐                                     │
│  │ BaseSink        │  Abstract base class                │
│  │ (Interface)     │                                     │
│  └────────┬────────┘                                     │
│           │                                               │
│           │ Implements                                    │
│           │                                               │
│  ┌────────▼──────────────────────────────────────────┐  │
│  │  Concrete Sink Implementations                    │  │
│  │  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │  SlackSink   │  │  JiraSink    │ ...          │  │
│  │  └──────────────┘  └──────────────┘              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────┐               │
│  │  Data Transformation                  │               │
│  │  - Format conversion                  │               │
│  │  - Payload adapters                   │               │
│  │  - Template rendering                 │               │
│  └───────────────────────────────────────┘               │
│                                                           │
│  ┌───────────────────────────────────────┐               │
│  │  Destination Integration              │               │
│  │  - API clients                        │               │
│  │  - Authentication                     │               │
│  │  - Error handling & retry             │               │
│  └───────────────────────────────────────┘               │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

#### Sink Interface

```python
class BaseSink:
    def send_data(
        self,
        analyzer_response_list: List[TextPayload],
        sink_config: SinkConfig
    ) -> List[str]:
        """
        Send analyzed data to destination
        
        Returns:
            List of response IDs/confirmations
        """
        pass
```

---

## Data Flow

### End-to-End Data Flow

```
1. Configuration
   ┌─────────────────┐
   │ User Config     │
   │ - Source params │
   │ - Analyzer opts │
   │ - Sink settings │
   └────────┬────────┘
            │
            ▼
2. Source Lookup
   ┌─────────────────┐
   │ External API    │◀─── Credentials
   │ Call            │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Raw Data        │
   │ (Platform fmt)  │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ TextPayload     │
   │ normalization   │
   └────────┬────────┘
            │
            ▼
3. Analysis
   ┌─────────────────┐
   │ Preprocessing   │ (Optional)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ ML Model        │
   │ Inference       │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Postprocessing  │ (Optional)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ TextPayload     │
   │ + segmented_data│
   └────────┬────────┘
            │
            ▼
4. Sink Delivery
   ┌─────────────────┐
   │ Format          │
   │ Conversion      │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Destination API │
   │ Call            │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Response        │
   │ Confirmation    │
   └─────────────────┘
```

---

## Data Models

### Core Data Model: TextPayload

```python
class BasePayload(BaseModel):
    segmented_data: Dict[str, Any] = {}  # Analysis results
    meta: Dict[str, Any] = {}            # Metadata
    source_name: Optional[str] = "Undefined"

class TextPayload(BasePayload):
    processed_text: str                  # Main text content
```

### Analysis Result Structure

```python
{
    "processed_text": "Customer review text...",
    "segmented_data": {
        "classifier_data": {
            "labels": ["complaint", "bug", "positive"],
            "scores": [0.85, 0.10, 0.05]
        },
        "sentiment_data": {
            "sentiment": "negative",
            "score": -0.45
        },
        "ner_data": {
            "entities": [
                {"text": "iPhone", "label": "PRODUCT"},
                {"text": "Apple", "label": "ORG"}
            ]
        }
    },
    "meta": {
        "source": "twitter",
        "timestamp": "2025-11-16T10:30:00Z",
        "user_id": "12345",
        "original_url": "https://..."
    },
    "source_name": "TwitterSource"
}
```

---

## State Management

### State Persistence Architecture

```
┌──────────────────────────────────────────────────────┐
│              WorkflowStore                            │
├──────────────────────────────────────────────────────┤
│                                                        │
│  ┌────────────────────────────────────────────┐      │
│  │  State Schema                              │      │
│  │  - workflow_id (unique identifier)         │      │
│  │  - last_fetch_timestamp                    │      │
│  │  - cursor/offset                           │      │
│  │  - metadata (JSON)                         │      │
│  └────────────────────────────────────────────┘      │
│                                                        │
│  ┌────────────────────────────────────────────┐      │
│  │  Database Backend (via SQLAlchemy)         │      │
│  │  - SQLite (default, file-based)            │      │
│  │  - PostgreSQL (production)                 │      │
│  │  - MySQL                                   │      │
│  └────────────────────────────────────────────┘      │
│                                                        │
└──────────────────────────────────────────────────────┘
```

### State Flow

```
First Run:
  No state exists → Fetch data from lookup_period → Save state

Subsequent Runs:
  State exists → Fetch only new data since last state → Update state

State Update:
  Transaction:
    1. Read current state
    2. Fetch new data
    3. Process data
    4. Update state with new timestamp/cursor
    5. Commit
```

---

## Processing Patterns

### Pattern 1: Linear Pipeline

```
Source → Analyzer → Sink
```

Simplest pattern for straightforward workflows.

### Pattern 2: Multi-Source Aggregation

```
Source 1 ─┐
Source 2 ─┼→ Analyzer → Sink
Source 3 ─┘
```

Collect from multiple sources, analyze together.

### Pattern 3: Multi-Analyzer Chain

```
            ┌→ Sentiment Analyzer ─┐
Source → ─┼→ Classification Analyzer ─┼→ Sink
            └→ NER Analyzer ─────────┘
```

Apply multiple analyzers to the same data.

### Pattern 4: Conditional Routing

```
Source → Analyzer → Filter → [Condition] → Sink 1
                                         └→ Sink 2
```

Route to different sinks based on analysis results.

### Pattern 5: Preprocessing Pipeline

```
Source → Text Cleaner → Text Splitter → Analyzer → Aggregator → Sink
```

Complex text processing with preprocessing and postprocessing.

---

## Scalability Considerations

### Horizontal Scaling

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│ Worker 1   │     │ Worker 2   │     │ Worker 3   │
│ (Instance) │     │ (Instance) │     │ (Instance) │
└──────┬─────┘     └──────┬─────┘     └──────┬─────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                          ▼
                 ┌────────────────┐
                 │  Shared State  │
                 │    Storage     │
                 └────────────────┘
```

Multiple instances can process different sources/keywords in parallel, sharing state storage.

### Vertical Scaling

- **GPU Acceleration**: Use powerful GPUs for model inference
- **Batch Processing**: Process multiple items together
- **Model Optimization**: Use quantized or distilled models

---

## Security Architecture

### Authentication Flow

```
┌─────────────┐
│   Obsei     │
│ Application │
└──────┬──────┘
       │
       │ 1. Load credentials
       ▼
┌─────────────────┐
│ Credential Store│
│ (env vars, etc) │
└──────┬──────────┘
       │
       │ 2. Authenticate
       ▼
┌─────────────────┐
│  External API   │
│   (Twitter,     │
│   Reddit, etc)  │
└──────┬──────────┘
       │
       │ 3. Return token/session
       ▼
┌─────────────────┐
│  Authenticated  │
│    Requests     │
└─────────────────┘
```

### PII Handling

```
Input Text
    │
    ▼
┌──────────────────┐
│ PII Detection    │ (Presidio Analyzer)
│ - Names          │
│ - Emails         │
│ - Phone numbers  │
│ - SSN, etc.      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ PII Anonymization│ (Presidio Anonymizer)
│ - Replace        │
│ - Redact         │
│ - Hash           │
└────────┬─────────┘
         │
         ▼
    Clean Text
```

---

## Error Handling Strategy

### Error Hierarchy

```
ObseiException (Base)
    │
    ├── SourceException
    │   ├── AuthenticationError
    │   ├── RateLimitError
    │   └── DataFetchError
    │
    ├── AnalyzerException
    │   ├── ModelLoadError
    │   ├── InferenceError
    │   └── DeviceError
    │
    └── SinkException
        ├── DeliveryError
        ├── FormatError
        └── DestinationError
```

### Error Flow

```
Try:
    Source.lookup()
Except SourceException:
    Log error
    Retry with exponential backoff
    Send alert if max retries exceeded

Try:
    Analyzer.analyze()
Except AnalyzerException:
    Log error
    Use fallback analyzer (if configured)
    Or skip and continue

Try:
    Sink.send_data()
Except SinkException:
    Log error
    Queue for later retry
    Use backup sink (if configured)
```

---

## Performance Optimization

### Model Caching

```
First Request:
    Download model from HuggingFace → Cache locally → Load → Inference

Subsequent Requests:
    Load from cache → Inference
```

### Batch Processing

```python
# Instead of:
for item in items:
    result = analyzer.analyze(item)

# Do:
results = analyzer.analyze_batch(items, batch_size=32)
```

### GPU Memory Management

```
┌─────────────────────────────────────┐
│  GPU Memory Optimization            │
├─────────────────────────────────────┤
│ 1. Use smaller models               │
│ 2. Enable model quantization        │
│ 3. Process in batches               │
│ 4. Clear cache between batches     │
│ 5. Use mixed precision (FP16)      │
└─────────────────────────────────────┘
```

---

## Testing Architecture

### Test Layers

```
┌────────────────────────────────────┐
│  Unit Tests                        │
│  - Individual components           │
│  - Mock external dependencies      │
└────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Integration Tests                 │
│  - Component interactions          │
│  - End-to-end workflows            │
└────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  System Tests                      │
│  - Full workflows with real APIs   │
│  - Performance tests               │
└────────────────────────────────────┘
```

---

## Deployment Patterns

### Pattern 1: Scheduled Jobs (Cron)

```
┌─────────────────┐
│  Cron Schedule  │
│  (Hourly/Daily) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Execute Workflow│
│ - Fetch         │
│ - Analyze       │
│ - Send          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Update State   │
└─────────────────┘
```

### Pattern 2: Serverless (AWS Lambda, Azure Functions)

```
┌─────────────────┐
│  Event Trigger  │
│  (CloudWatch)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Lambda Function │
│ (Obsei workflow)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DynamoDB/RDS    │
│ (State storage) │
└─────────────────┘
```

### Pattern 3: Long-Running Service

```
┌─────────────────┐
│  Daemon Process │
│  (systemd)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Continuous     │
│  Monitoring     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Process Events  │
│ in real-time    │
└─────────────────┘
```

---

## Extension Points

### Custom Source

```python
from obsei.source.base_source import BaseSource

class MyCustomSource(BaseSource):
    def lookup(self, config):
        # Implement your data fetching logic
        return [TextPayload(...)]
```

### Custom Analyzer

```python
from obsei.analyzer.base_analyzer import BaseAnalyzer

class MyCustomAnalyzer(BaseAnalyzer):
    def analyze_input(self, source_response_list, config):
        # Implement your analysis logic
        return analyzed_payloads
```

### Custom Sink

```python
from obsei.sink.base_sink import BaseSink

class MyCustomSink(BaseSink):
    def send_data(self, analyzer_response_list, config):
        # Implement your delivery logic
        return response_ids
```

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Language** | Python 3.8+ |
| **ML/AI** | PyTorch, Transformers, spaCy, NLTK |
| **Data Processing** | Pandas, NumPy |
| **Web/API** | Requests, BeautifulSoup4 |
| **Database** | SQLAlchemy (ORM), SQLite/PostgreSQL/MySQL |
| **Configuration** | Pydantic (validation), python-dotenv |
| **Testing** | Pytest, Coverage |
| **Code Quality** | Black, MyPy, Pre-commit |
| **Build** | Hatchling (PEP 517) |
| **CI/CD** | GitHub Actions |

---

## Conclusion

Obsei's architecture is designed for:

- **Modularity**: Easy to add new sources, analyzers, and sinks
- **Extensibility**: Well-defined interfaces for custom components
- **Scalability**: Support for both vertical and horizontal scaling
- **Reliability**: State management prevents data loss
- **Flexibility**: Multiple deployment patterns supported

The architecture follows clean separation of concerns with minimal coupling between components, making it easy to maintain and extend.

---

**Document Version**: 1.0  
**Last Updated**: November 16, 2025
