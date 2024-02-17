from typing import List, Any
from api.src.interfaces.usecase.listening_config_usecase import (
    StoreListeningConfigUseCase,
    UpdateListeningConfigUseCase,
    DeleteListeningConfigUseCase,
    GetListeningConfigByIdUseCase,
)

from api.src.interfaces.usecase.listening_config_data import (
    StoreListeningConfigInputData,
    StoreListeningConfigOutData,
    UpdateListeningConfigInputData,
    GetListeningConfigOutData,
)

from api.src.interfaces.usecase.execute_listening_usecase import (
    GetUrlByKeywordsUseCase,
    SaveUrlByKeywordsUseCase,
    ExecuteListeningUseCase,
    GetDataExecutedByConfigIdUseCase,
)
from api.src.schema.listening_config import (
    Analyzer,
    AnalyzerConfig,
    Source,
    SourceConfig,
    Sink,
    SinkConfig,
)

from api.src.interfaces.usecase.result_data import (
    ResultData,
)


class ConfigService:
    def __init__(
            self,
            store_listening_config_use_case: StoreListeningConfigUseCase = None,
            update_listening_config_use_case: UpdateListeningConfigUseCase = None,
            delete_listening_config_use_case: DeleteListeningConfigUseCase = None,
            get_listening_config_by_id_use_case: GetListeningConfigByIdUseCase = None,
            get_url_by_keywords_use_case: GetUrlByKeywordsUseCase = None,
            save_url_video_by_keywords_use_case: SaveUrlByKeywordsUseCase = None,
            execute_listening_use_case: ExecuteListeningUseCase = None,
            get_data_executed_by_config_id_use_case: GetDataExecutedByConfigIdUseCase = None,

    ):
        self.store_listening_config_use_case = store_listening_config_use_case
        self.update_listening_config_use_case = update_listening_config_use_case
        self.delete_listening_config_use_case = delete_listening_config_use_case
        self.get_listening_config_by_id_use_case = get_listening_config_by_id_use_case
        self.get_url_by_keywords_use_case = get_url_by_keywords_use_case
        self.save_url_video_by_keywords_use_case = save_url_video_by_keywords_use_case
        self.execute_listening_use_case = execute_listening_use_case
        self.get_data_executed_by_config_id_use_case = get_data_executed_by_config_id_use_case

    def store_listening_config(
            self,
            user_id: str,
            source: Source,
            source_config: SourceConfig,
            analyzer: Analyzer,
            analyzer_config: AnalyzerConfig,
            sink: Sink,
            sink_config: SinkConfig,
            db
    ) -> StoreListeningConfigOutData:
        input = StoreListeningConfigInputData(source=source, source_config=source_config, analyzer=analyzer,
                                              analyzer_config=analyzer_config, sink=sink,
                                              sink_config=sink_config,
                                              user_id=user_id)

        return self.store_listening_config_use_case.handle(input, db=db)

    def update_listening_config(
            self,
            config_id: str,
            source: Source,
            source_config: SourceConfig,
            analyzer: Analyzer,
            analyzer_config: AnalyzerConfig,
            sink: Sink,
            sink_config: SinkConfig,
            db
    ) -> GetListeningConfigOutData:
        input = UpdateListeningConfigInputData(source=source, source_config=source_config,
                                               analyzer=analyzer,
                                               analyzer_config=analyzer_config, sink=sink,
                                               sink_config=sink_config)

        return self.update_listening_config_use_case.handle(config_id, input, db=db)

    def delete_listening_config(self, config_id: str, db) -> ResultData:
        return self.delete_listening_config_use_case.handle(config_id, db=db)

    def get_listening_config_by_id(self, config_id: str, db) -> GetListeningConfigOutData:
        return self.get_listening_config_by_id_use_case.handle(config_id, db=db)

    def get_url_video_by_keywords(self, config: GetListeningConfigOutData) -> GetListeningConfigOutData:
        return self.get_url_by_keywords_use_case.handle(config)

    def save_url_video_by_keywords(self, config_id: str, source_config: object, db) -> list[dict[str, Any] | dict[
        str, Any]] | list[Any]:
        return self.save_url_video_by_keywords_use_case.handle(config_id, source_config, db=db)

    def execute_listening(self, config_id: str) -> None:
        return self.execute_listening_use_case.handle(config_id)

    def get_data_executed_by_config_id(self, config_id: str, db) -> object:
        return self.get_data_executed_by_config_id_use_case.handle(config_id, db=db)
