import logging
import sys
from datetime import datetime, timedelta

import pytz

from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig, ZeroShotClassificationAnalyzer
from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.source.playstore_scrapper import PlayStoreScrapperConfig, PlayStoreScrapperSource


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

since_time = datetime.utcnow().astimezone(pytz.utc) + timedelta(days=-4)
source_config = PlayStoreScrapperConfig(
    countries=["us"],
    package_name="com.apcoaconnect",
    lookup_period=since_time.strftime(DATETIME_STRING_PATTERN)
)

source = PlayStoreScrapperSource()

text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="joeddav/bart-large-mnli-yahoo-answers",
    device="auto"
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=ClassificationAnalyzerConfig(
        labels=["no parking", "registration issue", "app issue", "payment issue"],
    )
)
for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")

