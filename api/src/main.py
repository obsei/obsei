from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from logging import INFO, Formatter, StreamHandler, getLogger
from api.src.driver.nosql import DatabaseConnector
from api.src.interfaces.data.const import (
    DEFAULT_TIMEZONE,
    DEFAULT_MAX_AGE_HSTS
)
import secure
import api.src.routes.listening_config
import api.src.routes.execute_scrapper
from api.src.utils.app import check_basic_authentication


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

app = FastAPI()

app.include_router(api.src.routes.listening_config.router, dependencies=[Depends(check_basic_authentication)])
app.include_router(api.src.routes.execute_scrapper.router, dependencies=[Depends(check_basic_authentication)])

secure_headers = secure.Secure(
    hsts=secure.StrictTransportSecurity().max_age(DEFAULT_MAX_AGE_HSTS).include_subdomains(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware("http")
async def set_secure_headers(request, call_next):
    response = await call_next(request)
    secure_headers.framework.fastapi(response)
    return response


database_connector = DatabaseConnector()


@app.get("/")
async def root(
        client: DatabaseConnector.connect = Depends(database_connector.connect),
        _=Depends(check_basic_authentication),
):
    result = client.obsei.urls.find({})
    logger.info('-' * 20 + str(result) + '-' * 20)
    return {"message": "Hello World"}
