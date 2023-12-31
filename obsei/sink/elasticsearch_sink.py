from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from elasticsearch import Elasticsearch, RequestError
from elasticsearch.helpers import bulk
from pydantic import Field, PrivateAttr, SecretStr

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.payload import TextPayload


class ElasticSearchSinkConfig(BaseSinkConfig):
    # This is done to avoid exposing member to API response
    _es_client: Elasticsearch = PrivateAttr()
    TYPE: str = "Elasticsearch"
    hosts: Union[str, List[str], None]
    index_name: str = "es_index"
    username: SecretStr = Field(SecretStr(""), env="elasticsearch_username")
    password: SecretStr = Field(SecretStr(""), env="elasticsearch_password")
    ca_certs: str = Field("<DEFAULT>")
    verify_certs: bool = False
    create_index: bool = True
    timeout: int = 30
    custom_mapping: Optional[Dict[str, Any]] = None
    refresh_type: str = "wait_for"
    base_payload: Optional[Dict[str, Any]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._es_client = Elasticsearch(
            hosts=self.hosts,
            http_auth=(
                self.username.get_secret_value(),
                self.password.get_secret_value(),
            ),
            ca_certs=self.ca_certs,
            verify_certs=self.verify_certs,
            timeout=self.timeout,
        )
        self.base_payload = self.base_payload or {
            "_op_type": "create",  # TODO update exiting support?
            "_index": self.index_name,
        }
        if self.create_index:
            self._create_index(self.index_name)

    def _create_index(self, index_name: str) -> None:
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
                                "mapping": {"type": "keyword"},
                            }
                        }
                    ],
                }
            }

        try:
            self._es_client.indices.create(index=index_name, mappings=mapping)
        except RequestError as e:
            # With multiple workers we need to avoid race conditions, where:
            # - there's no index in the beginning
            # - both want to create one
            # - one fails as the other one already created it
            if not self._es_client.indices.exists(index=index_name):
                raise e

    def bulk(self, payloads: List[Dict[str, Any]]) -> Any:
        return bulk(
            self._es_client, payloads, request_timeout=300, refresh=self.refresh_type
        )


class ElasticSearchSink(BaseSink):
    def __init__(self, convertor: Convertor = Convertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
        config: ElasticSearchSinkConfig,
        **kwargs: Any
    ) -> Any:

        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(
                self.convertor.convert(
                    analyzer_response=analyzer_response,
                    base_payload=deepcopy(config.base_payload),
                )
            )

        return config.bulk(payloads)
