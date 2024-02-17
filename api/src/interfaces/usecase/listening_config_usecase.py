from abc import ABCMeta
from api.src.interfaces.usecase.listening_config_data import (
    StoreListeningConfigInputData,
    StoreListeningConfigOutData,
    UpdateListeningConfigInputData,
    GetListeningConfigOutData,
)

from api.src.interfaces.usecase.result_data import (
    ResultData,
)


class GetListeningConfigByIdUseCase(metaclass=ABCMeta):
    def handle(self, config_if: str, db) -> GetListeningConfigOutData:
        raise NotImplementedError


class StoreListeningConfigUseCase(metaclass=ABCMeta):
    def handle(self, input_data: StoreListeningConfigInputData, db) -> StoreListeningConfigOutData:
        raise NotImplementedError


class UpdateListeningConfigUseCase(metaclass=ABCMeta):
    def handle(self, config_id: str, input_data: UpdateListeningConfigInputData, db) -> GetListeningConfigOutData:
        raise NotImplementedError


class DeleteListeningConfigUseCase(metaclass=ABCMeta):
    def handle(self, config_id: str, db) -> ResultData:
        raise NotImplementedError
