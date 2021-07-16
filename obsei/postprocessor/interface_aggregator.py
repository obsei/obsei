from obsei.postprocessor.base_postprocessor import (
    BasePostprocessorConfig,
    BasePostprocessor,
    TextPayload,
)
from typing import Any, List, Optional


class InterfaceAggregatorConfig(BasePostprocessorConfig):
    aggregation_method = "most_common"

    def __init__(self, **data):
        super().__init__(**data)


class InterfaceAggregator(BasePostprocessor):
    def postprocess_input(
        self, input_list: List[TextPayload], config: InterfaceAggregatorConfig, **kwargs
    ) -> List[TextPayload]:
        prev_document_id = -1
        document = []
        aggregated_payloads = []
        for output in input_list:
            if prev_document_id == -1:
                prev_document_id = output.meta["document_id"]
                document.append(output)

            elif prev_document_id == output.meta["document_id"]:
                document.append(output)
            else:
                aggregated_payloads.append(document)
                document = [output]
                prev_document_id = output.meta["document_id"]

        if document and not aggregated_payloads:
            aggregated_payloads.append(document)

        return [
            self._process_scores(config.aggregation_method, doc)
            for doc in aggregated_payloads
        ]

    def _process_scores(self, stratergy, documents):
        if stratergy == "most_common":
            return self._most_common(documents)
        if stratergy == "weighted_average":
            return self._weighted_average(documents)
        return None

    def _most_common(self, documents):
        labels = []
        doc_text = []
        doc_id = documents[0].meta["document_id"]
        source_name = documents[0].source_name

        for doc in documents:
            doc_text.append(doc.processed_text)
            scores = doc.segmented_data
            scores = {
                key: value
                for key, value in scores.items()
                if key not in ["positive", "negative"]
            }
            max_key = max(scores, key=scores.get)
            labels.append(max_key)
        label = max(labels, key=labels.count)
        return TextPayload(
            processed_text=" ".join(doc_text),
            meta={"document_id": doc_id, "label": label},
            source_name=source_name,
        )

    def _weighted_average(self, documents):
        if len(documents) == 0:
            return None
        doc_id = documents[0].meta["document_id"]
        document_length = documents[0].meta["document_length"]
        source_name = documents[0].source_name
        scores = {key: 0 for key in documents[0].segmented_data.keys()}
        doc_text = []
        for doc in documents:

            doc_text.append(doc.processed_text)
            for key in scores.keys():
                scores[key] += (
                    doc.meta["text_length"] / document_length
                ) * doc.segmented_data[key]

        scores = {
            key: value
            for key, value in scores.items()
            if key not in ["positive", "negative"]
        }
        max_key = max(scores, key=scores.get)
        return TextPayload(
            processed_text=" ".join(doc_text),
            meta={"label": max_key, "document_id": doc_id},
            segmented_data=scores,
            source_name=source_name,
        )
