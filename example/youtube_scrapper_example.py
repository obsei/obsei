import logging
import sys

from obsei.analyzer.classification_analyzer import (
    ClassificationAnalyzerConfig, ZeroShotClassificationAnalyzer)
from obsei.source.youtube_scrapper import (YoutubeScrapperConfig,
                                           YoutubeScrapperSource)

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = YoutubeScrapperConfig(
    video_url="https://www.youtube.com/watch?v=uZfns0JIlFk",
    fetch_replies=True,
    max_comments=10,
    lookup_period="1Y",
)

source = YoutubeScrapperSource()

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli", device="auto"
)

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=ClassificationAnalyzerConfig(
        labels=["interesting", "enquiring"],
    ),
)
for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")
