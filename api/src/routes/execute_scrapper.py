from fastapi import APIRouter, HTTPException, Depends
from logging import INFO, Formatter, StreamHandler, getLogger
from api.src.utils.app import check_basic_authentication
from api.src.driver.nosql import DatabaseConnector
from api.src.service.config_service import ConfigService
from fastapi.responses import JSONResponse
from api.src.interfaces.usecase.execute_listening_data import (
    ExecuteListeningOutData,
)
from api.src.implement.interactor.execute_listening.rdb_execute_listening_interactor import (
    RDBGetUrlByKeywordsInteractor,
    RDBSaveUrlVideoByKeywordsInteractor,
    RDBExecuteListeningInteractor,
)

from api.src.implement.interactor.listening_config.rdb_listening_config_interactor import (
    RDBGetListeningConfigByIdInteractor,
)

import pymongo

router = APIRouter(
    prefix="/listening",
    tags=["Social Listening"],
    responses={404: {"description": "Not found"}},
)


def _set_handler(logger, handler):
    handler.setLevel(INFO)
    handler.setFormatter(Formatter(
        '%(name)s: %(funcName)s '
        '[%(levelname)s]: %(message)s'))
    logger.addHandler(handler)
    return logger


logger = getLogger(__name__)
logger = _set_handler(logger, StreamHandler())
logger.setLevel(INFO)
logger.propagate = False

database_connector = DatabaseConnector()


@router.post("/execute/{config_id}", response_model=ExecuteListeningOutData)
def store(
        config_id: str,
        client: DatabaseConnector.connect = Depends(database_connector.connect),
        _=Depends(check_basic_authentication),
):
    logger.info('-' * 20 + 'POST /listening/execute/' + '-' * 20)
    try:
        execute_service = ConfigService(
            get_listening_config_by_id_use_case=RDBGetListeningConfigByIdInteractor(),
            get_url_by_keywords_use_case=RDBGetUrlByKeywordsInteractor(),
            save_url_video_by_keywords_use_case=RDBSaveUrlVideoByKeywordsInteractor(),
            execute_listening_use_case=RDBExecuteListeningInteractor(),
        )
        database = client.obsei

        config = execute_service.get_listening_config_by_id(config_id, database)
        generated_config = execute_service.get_url_video_by_keywords(config)

        source_config = generated_config.source_config

        execute_service.save_url_video_by_keywords(config_id, source_config, database)
        execute_service.execute_listening(config_id)

        logger.info('-' * 20 + 'POST  /listening/execute/' + ' Response' + '-' * 20)

        return JSONResponse({'status': True, 'message': "Social listening is processing, please wait."})
    except pymongo.errors.PyMongoError as e:
        raise HTTPException(status_code=400, detail=f"{str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}")
    finally:
        pass
