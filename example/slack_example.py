import logging
import os
import sys
from datetime import datetime, timedelta

import pytz

from obsei.analyzer.dummy_analyzer import DummyAnalyzer, DummyAnalyzerConfig
from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.processor import Processor
from obsei.sink.slack_sink import SlackSink, SlackSinkConfig
from obsei.source.reddit_source import RedditConfig, RedditSource
from obsei.workflow.store import WorkflowStore
from obsei.workflow.workflow import Workflow, WorkflowConfig


def print_state(id: str):
    logger.info(f"Source State: {source.store.get_source_state(id)}")


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

since_time = datetime.utcnow().astimezone(pytz.utc) + timedelta(hours=-1)

workflow_store = WorkflowStore()

source_config = RedditConfig(
    subreddits=["wallstreetbets"],
    lookup_period=since_time.strftime(DATETIME_STRING_PATTERN),
)

source = RedditSource(store=workflow_store)

sink_config = SlackSinkConfig(
    slack_token=os.environ["SLACK_TOKEN"], channel_id="C01LRS6CT9Q"
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
