from fastapi import APIRouter, HTTPException, Depends
from logging import INFO, Formatter, StreamHandler, getLogger
from api.src.utils.app import check_basic_authentication
from api.src.driver.nosql import DatabaseConnector
from api.src.service.config_service import ConfigService
from fastapi.responses import JSONResponse
from api.src.domain.exceptions import (
    DataListeningConfigNotFound,
)
from api.src.interfaces.usecase.listening_config_data import (
    StoreListeningConfigOutData,
    GetListeningConfigOutData,
)
from api.src.schema.listening_config import (
    CreateListeningConfigRequestBody,
    UpdateListeningConfigRequestBody
)
from api.src.implement.interactor.listening_config.rdb_listening_config_interactor import (
    RDBStoreListeningConfigInteractor,
    RDBUpdateListeningConfigInteractor,
    RDBDeleteListeningConfigInteractor,
)
import pymongo

router = APIRouter(
    prefix="/listening_config",
    tags=["Generate Config"],
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


@router.post("/store", response_model=StoreListeningConfigOutData)
def store(
        request: CreateListeningConfigRequestBody,
        client: DatabaseConnector.connect = Depends(database_connector.connect),
        _=Depends(check_basic_authentication),
):
    logger.info('-' * 20 + 'POST /listening_config/store/' + '-' * 20)
    logger.info(f'store for user: {request.user_id}')
    try:
        listening_config_service = ConfigService(
            store_listening_config_use_case=RDBStoreListeningConfigInteractor(),
        )

        with client.start_session() as session:
            with session.start_transaction():
                result = listening_config_service.store_listening_config(
                    user_id=request.user_id,
                    source=request.source,
                    source_config=request.source_config,
                    analyzer=request.analyzer,
                    analyzer_config=request.analyzer_config,
                    sink=request.sink,
                    sink_config=request.sink_config,
                    db=client.obsei
                )
        response = {
            'generate_config_id': str(result.id),
        }

        logger.info('-' * 20 + 'POST  /listening_config/store/' + ' Response' + '-' * 20)
        logger.info(response)
        return JSONResponse(response)
    except pymongo.errors.PyMongoError as e:
        raise HTTPException(status_code=400, detail=f"{str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}")
    finally:
        pass


@router.put("/update/{config_id}", response_model=GetListeningConfigOutData)
def update(
        request: UpdateListeningConfigRequestBody,
        config_id: str,
        client: DatabaseConnector.connect = Depends(database_connector.connect),
        _=Depends(check_basic_authentication)
):
    logger.info('-' * 20 + 'PUT /listening_config/update/' + '-' * 20)
    logger.info(f'update for config: {config_id}')
    try:
        listening_config_service = ConfigService(
            update_listening_config_use_case=RDBUpdateListeningConfigInteractor(),
        )

        with client.start_session() as session:
            with session.start_transaction():
                result = listening_config_service.update_listening_config(
                    config_id=config_id,
                    source=request.source,
                    source_config=request.source_config,
                    analyzer=request.analyzer,
                    analyzer_config=request.analyzer_config,
                    sink=request.sink,
                    sink_config=request.sink_config,
                    db=client.obsei
                )
        response = {
            'generate_config_id': str(result.id),
            'source': result.source,
            'source_config': result.source_config,
            'analyzer': result.analyzer,
            'analyzer_config': result.analyzer_config,
            'sink': result.sink,
            'sink_config': result.sink_config,
            'user_id': result.user_id
        }

        logger.info('-' * 20 + 'POST  /listening_config/update/' + ' Response' + '-' * 20)
        logger.info(response)
        return JSONResponse(response)
    except DataListeningConfigNotFound:
        raise HTTPException(status_code=404, detail=f"No config was found for id {config_id}.")
    except pymongo.errors.PyMongoError as e:
        raise HTTPException(status_code=400, detail=f"{e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")
    finally:
        pass


@router.delete("/delete/{config_id}")
def update(
        config_id: str,
        client: DatabaseConnector.connect = Depends(database_connector.connect),
        _=Depends(check_basic_authentication)
):
    logger.info('-' * 20 + 'DELETE /listening_config/delete/' + '-' * 20)
    logger.info(f'delete config: {config_id}')
    try:
        listening_config_service = ConfigService(
            delete_listening_config_use_case=RDBDeleteListeningConfigInteractor(),
        )

        with client.start_session() as session:
            with session.start_transaction():
                listening_config_service.delete_listening_config(config_id, client.obsei)

        logger.info('-' * 20 + 'DELETE  /listening_config/delete/' + ' Response' + '-' * 20)
        return JSONResponse({'message': 'Delete listening config successfully'})
    except DataListeningConfigNotFound:
        raise HTTPException(status_code=404, detail=f"No config was found for id {config_id}.")
    except pymongo.errors.PyMongoError as e:
        raise HTTPException(status_code=400, detail=f"{e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")
    finally:
        pass
