from typing import Any, List, Optional

from obsei.analyzer.base_analyzer import AnalyzerRequest, AnalyzerResponse, BaseAnalyzer, BaseAnalyzerConfig


class DummyAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "Dummy"
    dummy_data: Optional[Any] = None

    def __init__(self, **data: Any):
        super().__init__(**data)


class DummyAnalyzer(BaseAnalyzer):
    def analyze_input(
        self, source_response_list: List[AnalyzerRequest],
        analyzer_config: DummyAnalyzerConfig,
        **kwargs
    ) -> List[AnalyzerResponse]:
        responses = []
        for source_response in source_response_list:
            responses.append(
                AnalyzerResponse(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    source_name=source_response.source_name,
                    segmented_data={"data": analyzer_config.dummy_data}
                )
            )

        return responses
