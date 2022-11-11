import logging

from obsei.analyzer.base_analyzer import BaseAnalyzer, BaseAnalyzerConfig
from obsei.configuration import ObseiConfiguration
from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.source.base_source import BaseSourceConfig, BaseSource

logger = logging.getLogger(__name__)

# Extract config via yaml file using `config_path` and `config_filename`
obsei_configuration = ObseiConfiguration()

# Initialize objects using configuration
source_config: BaseSourceConfig = obsei_configuration.initialize_instance("source_config")
source: BaseSource = obsei_configuration.initialize_instance("source")
analyzer: BaseAnalyzer = obsei_configuration.initialize_instance("analyzer")
analyzer_config: BaseAnalyzerConfig = obsei_configuration.initialize_instance("analyzer_config")
sink_config: BaseSinkConfig = obsei_configuration.initialize_instance("sink_config")
sink: BaseSink = obsei_configuration.initialize_instance("sink")

# This will fetch information from configured source ie twitter, app store etc
source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{vars(source_response)}'")

# This will execute analyzer (Sentiment, classification etc) on source data with provided analyzer_config
# Analyzer will it's output to `segmented_data` inside `analyzer_response`
analyzer_response_list = analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config
)
for idx, analyzer_response in enumerate(analyzer_response_list):
    logger.info(f"source_response#'{idx}'='{vars(analyzer_response)}'")

# This will send analyzed output to configure sink ie Slack, Zendesk etc
sink_response_list = sink.send_data(analyzer_response_list, sink_config)
for idx, sink_response in enumerate(sink_response_list):
    logger.info(f"source_response#'{idx}'='{vars(sink_response)}'")
