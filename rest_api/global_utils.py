import logging
from typing import Dict

from fastapi import APIRouter, FastAPI, HTTPException
from flask import Request
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from obsei.sink.base_sink import BaseSink
from obsei.sink.dailyget_sink import DailyGetSink
from obsei.sink.elasticsearch_sink import ElasticSearchSink
from obsei.sink.http_sink import HttpSink
from obsei.sink.jira_sink import JiraSink
from obsei.source.appstore_scrapper import AppStoreScrapperSource
from obsei.source.base_source import BaseSource
from obsei.source.playstore_reviews import PlayStoreSource
from obsei.source.playstore_scrapper import PlayStoreScrapperSource
from obsei.source.reddit_scrapper import RedditScrapperSource
from obsei.source.reddit_source import RedditSource
from obsei.source.twitter_source import TwitterSource

logger = logging.getLogger(__name__)

source_map: Dict[str, BaseSource] = {
    "Twitter": TwitterSource(),
    "PlayStore": PlayStoreSource(),
    "PlayStoreScrapper": PlayStoreScrapperSource(),
    "AppStoreScrapper": AppStoreScrapperSource(),
    "RedditScrapper": RedditScrapperSource(),
    "Reddit": RedditSource()
}

sink_map: Dict[str, BaseSink] = {
    "Http": HttpSink(),
    "Jira": JiraSink(),
    "DailyGet": DailyGetSink(),
    "Elasticsearch": ElasticSearchSink(),
}

router = APIRouter()


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"errors": [exc.detail]}, status_code=exc.status_code)


def get_application() -> FastAPI:
    application = FastAPI(
        title="Obsei-APIs",
        debug=True,
        description="Observe, Segment and Inform"
    )

    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    application.add_exception_handler(HTTPException, http_error_handler)

    application.include_router(router)

    return application
