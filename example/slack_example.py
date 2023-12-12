import logging
import os
import sys

from obsei.analyzer.dummy_analyzer import DummyAnalyzer, DummyAnalyzerConfig
from obsei.processor import Processor
from obsei.sink.slack_sink import SlackSink, SlackSinkConfig
from obsei.source.playstore_scrapper import (PlayStoreScrapperConfig,
                                             PlayStoreScrapperSource)
from obsei.workflow.store import WorkflowStore
from obsei.workflow.workflow import Workflow, WorkflowConfig


def print_state(identifier: str):
    logger.info(f"Source State: {source.store.get_source_state(identifier)}")


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


workflow_store = WorkflowStore()

source_config = PlayStoreScrapperConfig(
    app_url='https://play.google.com/store/apps/details?id=com.google.android.gm&hl=en_IN&gl=US',
    max_count=3
)

source = PlayStoreScrapperSource(store=workflow_store)

sink_config = SlackSinkConfig(
    slack_token=os.environ["SLACK_TOKEN"],
    channel_id="C01TUPZ23NZ",
    jinja_template="""
```
     {%- for key, value in payload.items() recursive%}
         {%- if value is mapping -%}
{{loop(value.items())}}
         {%- else %}
{{key}}: {{value}}
         {%- endif %}
     {%- endfor%}
```
   """
)
sink = SlackSink(store=workflow_store)

analyzer_config = DummyAnalyzerConfig()
analyzer = DummyAnalyzer()

workflow = Workflow(
    config=WorkflowConfig(
        source_config=source_config,
        sink_config=sink_config,
        analyzer_config=analyzer_config,
    ),
)
workflow_store.add_workflow(workflow)

processor = Processor(
    analyzer=analyzer, sink=sink, source=source, analyzer_config=analyzer_config
)

processor.process(workflow=workflow)

print_state(workflow.id)
