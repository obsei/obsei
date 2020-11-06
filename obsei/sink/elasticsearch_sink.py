from copy import deepcopy
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch, RequestError
from elasticsearch.helpers import bulk

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.text_analyzer import AnalyzerResponse


class ElasticSearchSinkConfig(BaseSinkConfig):
    def __init__(
        self,
        convertor: Convertor,
        host: str,
        port: int,
        index_name: str,
        username: str = "",
        password: str = "",
        scheme: str = "http",
        ca_certs: bool = False,
        verify_certs: bool = True,
        create_index: bool = True,
        timeout=30,
        custom_mapping: Optional[dict] = None,
        refresh_type: str = "wait_for",
        base_payload: Dict[str, Any] = None,
    ):
        self.es_client = Elasticsearch(
            hosts=[{"host": host, "port": port}],
            http_auth=(username, password),
            scheme=scheme,
            ca_certs=ca_certs,
            verify_certs=verify_certs,
            timeout=timeout
        )
        self.index_name: str = index_name
        self.custom_mapping = custom_mapping
        self.refresh_type = refresh_type
        self.base_payload = base_payload
        if create_index:
            self._create_index(index_name)

        super(ElasticSearchSinkConfig, self).__init__(convertor)

    def _create_index(self, index_name):
        if self.custom_mapping:
            mapping = self.custom_mapping
        else:
            mapping = {
                "mappings": {
                    "dynamic_templates": [
                        {
                            "strings": {
                                "path_match": "*",
                                "match_mapping_type": "string",
                                "mapping": {"type": "keyword"}}}
                    ],
                }
            }

        try:
            self.es_client.indices.create(index=index_name, body=mapping)
        except RequestError as e:
            # With multiple workers we need to avoid race conditions, where:
            # - there's no index in the beginning
            # - both want to create one
            # - one fails as the other one already created it
            if not self.es_client.indices.exists(index=index_name):
                raise e


class ElasticSearchSink(BaseSink):
    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: ElasticSearchSinkConfig, **kwargs):

        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(config.convertor.convert(
                analyzer_response=analyzer_response,
                base_payload=deepcopy(config.base_payload)
            ))

        return bulk(config.es_client, payloads, request_timeout=300, refresh=config.refresh_type)
