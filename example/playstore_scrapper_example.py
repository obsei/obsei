import logging
import sys

from obsei.analyzer.classification_analyzer import (
    ClassificationAnalyzerConfig,
    ZeroShotClassificationAnalyzer,
)

from obsei.source.playstore_scrapper import (
    PlayStoreScrapperConfig,
    PlayStoreScrapperSource,
)


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = PlayStoreScrapperConfig(
    app_url="https://play.google.com/store/apps/details?id=com.google.android.gm&hl=en_IN&gl=US",
    max_count=3,
)

source = PlayStoreScrapperSource()

text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli", device="auto"
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=ClassificationAnalyzerConfig(
        labels=["interface", "slow", "battery"],
    ),
)
for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")
