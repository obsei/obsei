import json
import logging
import sys
from datetime import datetime, timedelta

import pytz

from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.analyzer.classification_analyzer import (
    ClassificationAnalyzerConfig,
    ZeroShotClassificationAnalyzer,
)
from obsei.analyzer.translation_analyzer import TranslationAnalyzer
from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.source.playstore_scrapper import (
    PlayStoreScrapperConfig,
    PlayStoreScrapperSource,
)


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
source = PlayStoreScrapperSource()


def source_fetch():
    since_time = datetime.utcnow().astimezone(pytz.utc) + timedelta(days=-1)
    source_config = PlayStoreScrapperConfig(
        countries=["us"],
        package_name="com.color.apps.hindikeyboard.hindi.language",
        lookup_period=since_time.strftime(
            DATETIME_STRING_PATTERN
        ),  # todo should be optional
        max_count=5,
    )
    return source.lookup(source_config)


def translate_text(text_list):
    translate_analyzer = TranslationAnalyzer(
        model_name_or_path="Helsinki-NLP/opus-mt-hi-en", device="auto"
    )
    source_responses = [
        AnalyzerRequest(processed_text=text.processed_text, source_name="sample")
        for text in text_list
    ]
    analyzer_responses = translate_analyzer.analyze_input(
        source_response_list=source_responses
    )
    return [
        AnalyzerRequest(
            processed_text=response.segmented_data["translated_text"],
            source_name="translator",
        )
        for response in analyzer_responses
    ]


def classify_text(text_list):
    text_analyzer = ZeroShotClassificationAnalyzer(
        model_name_or_path="joeddav/bart-large-mnli-yahoo-answers", device="cpu"
    )

    return text_analyzer.analyze_input(
        source_response_list=text_list,
        analyzer_config=ClassificationAnalyzerConfig(
            labels=["no parking", "registration issue", "app issue", "payment issue"],
        ),
    )


def print_list(text_name, text_list):
    for idx, text in enumerate(text_list):
        json_response = json.dumps(text.__dict__, indent=4, sort_keys=True, default=str)
        logger.info(f"\n{text_name}#'{idx}'='{json_response}'")


logger.info("Started...")

source_responses_list = source_fetch()
translated_text_list = translate_text(source_responses_list)
analyzer_response_list = classify_text(translated_text_list)

print_list("source_response", source_responses_list)
print_list("translator_response", translated_text_list)
print_list("classifier_response", analyzer_response_list)
