import logging
import os

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import BaseScheduler
from fastapi import APIRouter, FastAPI, HTTPException
from flask import Request
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from obsei.processor import Processor
from obsei.text_analyzer import TextAnalyzer
from rest_api.rate_limiter import RequestLimiter

logger = logging.getLogger(__name__)

CONCURRENT_REQUEST_PER_WORKER = int(os.getenv("CONCURRENT_REQUEST_PER_WORKER", 4))
rate_limiter = RequestLimiter(CONCURRENT_REQUEST_PER_WORKER)

text_analyzer = TextAnalyzer(
    classifier_model_name="joeddav/bart-large-mnli-yahoo-answers",
    initialize_model=True,
)
processor = Processor(text_analyzer)

router = APIRouter()

job_stores = {
    'default': MemoryJobStore()
}
schedule: BaseScheduler = AsyncIOScheduler(jobstores=job_stores)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"errors": [exc.detail]}, status_code=exc.status_code)


def get_application() -> FastAPI:
    application = FastAPI(title="OBSEI-APIs", debug=True, version="0.1")

    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    application.add_exception_handler(HTTPException, http_error_handler)

    application.include_router(router)

    return application
