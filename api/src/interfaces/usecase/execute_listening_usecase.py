from abc import ABCMeta
from typing import List, Any
from api.src.interfaces.usecase.listening_config_data import (
    GetListeningConfigOutData,
)

from api.src.interfaces.usecase.result_data import (
    ResultData,
)


class GetUrlByKeywordsUseCase(metaclass=ABCMeta):
    def handle(self, config: GetListeningConfigOutData) -> GetListeningConfigOutData:
        raise NotImplementedError


class SaveUrlByKeywordsUseCase(metaclass=ABCMeta):
    def handle(self, config_id: str, source_config: object, db) -> list[dict[str, Any] | dict[str, Any]] | list[Any]:
        raise NotImplementedError


class ExecuteListeningUseCase(metaclass=ABCMeta):
    def handle(self, config_id: str) -> None:
        raise NotImplementedError


class GetDataExecutedByConfigIdUseCase(metaclass=ABCMeta):
    def handle(self, config_id: str, db) -> object:
        raise NotImplementedError
