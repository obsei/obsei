from typing import Any, List, Optional

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
)
from obsei.payload import TextPayload


class DummyAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "Dummy"
    dummy_data: Optional[Any] = None

    def __init__(self, **data: Any):
        super().__init__(**data)


class DummyAnalyzer(BaseAnalyzer):
    def analyze_input(  # type: ignore[override]
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[DummyAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        responses = []
        for source_response in source_response_list:

            segmented_data = {
                "dummy_data": None
                if not analyzer_config
                else analyzer_config.dummy_data
            }

            if source_response.segmented_data:
                segmented_data = {**segmented_data, **source_response.segmented_data}

            responses.append(
                TextPayload(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    source_name=source_response.source_name,
                    segmented_data=segmented_data,
                )
            )

        return responses
