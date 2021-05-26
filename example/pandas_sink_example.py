import logging
import sys

from pandas import DataFrame

from obsei.analyzer.classification_analyzer import (
    ClassificationAnalyzerConfig,
    ZeroShotClassificationAnalyzer,
)
from obsei.misc.utils import obj_to_json
from obsei.sink.pandas_sink import PandasSink, PandasSinkConfig
from obsei.source.playstore_scrapper import (
    PlayStoreScrapperConfig,
    PlayStoreScrapperSource,
)


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = PlayStoreScrapperConfig(
    countries=["us"], package_name="com.apcoaconnect", max_count=3
)

source = PlayStoreScrapperSource()

text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli", device="auto"
)

# initialize pandas sink config
sink_config = PandasSinkConfig(dataframe=DataFrame())

# initialize pandas sink
sink = PandasSink()

source_response_list = source.lookup(source_config)

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=ClassificationAnalyzerConfig(
        labels=["no parking", "registration issue", "app issue", "payment issue"],
    ),
)

dataframe = sink.send_data(
    analyzer_responses=analyzer_response_list, config=sink_config
)

print(dataframe.to_csv())
