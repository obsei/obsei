import logging
import os
from contextlib import contextmanager
from threading import Semaphore
from typing import Any, Dict, List

import uvicorn as uvicorn
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from obsei.processor import Processor
from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.sink.sink_utils import sink_config_from_dict
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.source.source_utils import source_config_from_dict
from obsei.text_analyzer import AnalyzerRequest, TextAnalyzer

logging.basicConfig(format="%(asctime)s %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p")
logger = logging.getLogger(__name__)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"errors": [exc.detail]}, status_code=exc.status_code)


class RequestLimiter:
    def __init__(self, limit):
        self.semaphore = Semaphore(limit - 1)

    @contextmanager
    def run(self):
        acquired = self.semaphore.acquire(blocking=False)
        if not acquired:
            raise HTTPException(status_code=503, detail="The server is busy processing requests.")
        try:
            yield acquired
        finally:
            self.semaphore.release()


class ClassifierRequest(BaseModel):
    texts: List[str]
    labels: List[str]
    use_sentiment_model: bool = True

    class Config:
        arbitrary_types_allowed = True


class SinkConfig(BaseModel):
    name: str
    config: Dict[str, Any]


class SourceConfig(BaseModel):
    name: str
    config: Dict[str, Any]


class ApplicationConfig(BaseModel):
    sink_config: SinkConfig
    source_config: SourceConfig
    time_in_seconds: int


current_config: ApplicationConfig

text_analyzer = TextAnalyzer(
    classifier_model_name="joeddav/bart-large-mnli-yahoo-answers",
    initialize_model=True,
)

sink: BaseSink
sink_config: BaseSinkConfig
source: BaseSource
source_config: BaseSourceConfig
processor = Processor(text_analyzer)

CONCURRENT_REQUEST_PER_WORKER = int(os.getenv("CONCURRENT_REQUEST_PER_WORKER", 4))
rate_limiter = RequestLimiter(CONCURRENT_REQUEST_PER_WORKER)

router = APIRouter()

Schedule = AsyncIOScheduler()
Schedule.start()
JOB_NAME = "obsei"


def process_scheduled_job():
    global current_config
    global processor

    try:
        if current_config:
            processor.process(
                sink=sink,
                sink_config=sink_config,
                source=source,
                source_config=source_config,
            )
    except Exception as ex:
        logger.error(f'Exception occur: {ex}')


def get_application() -> FastAPI:
    application = FastAPI(title="OBSEI-APIs", debug=True, version="0.1")

    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    application.add_exception_handler(HTTPException, http_error_handler)

    application.include_router(router)

    return application


app = get_application()


@app.on_event("startup")
async def load_schedule_or_create_blank():
    global Schedule
    try:
        jobstores = {
            'default': MemoryJobStore()
        }
        Schedule = AsyncIOScheduler(jobstores=jobstores)
        Schedule.start()
        logger.info("Created Schedule Object")
    except Exception as ex:
        logger.error("Unable to Create Schedule Object")


@app.get("/schedule/show_schedules/", tags=["schedule"])
async def get_scheduled_syncs():
    schedules = []
    for job in Schedule.get_jobs():
        schedules.append({"name": str(job.id), "run_frequency": str(job.trigger), "next_run": str(job.next_run_time)})
    return schedules


@app.post("/classifier", response_model=List[Dict[str, float]], response_model_exclude_unset=True, tags=["api"])
def classify_post(request: ClassifierRequest):
    with rate_limiter.run():
        analyzer_requests: List[AnalyzerRequest] = [
            AnalyzerRequest(
                processed_text=text,
                source_name="API"
            )
            for text in request.texts
        ]
        analyzer_responses = text_analyzer.analyze_input(
            source_response_list=analyzer_requests,
            labels=request.labels,
            use_sentiment_model=request.use_sentiment_model,
        )

        response = []
        for analyzer_response in analyzer_responses:
            response.append(analyzer_response.classification)

        return response


@app.post("/config", response_model=Dict[str, Any], response_model_exclude_unset=True, tags=["config"])
def classify_post(request: ApplicationConfig):
    with rate_limiter.run():
        global current_config
        global Schedule
        global sink
        global source
        global sink_config
        global source_config

        try:
            Schedule.remove_job(job_id=JOB_NAME)
        except JobLookupError as ex:
            logger.warning(f'Job {JOB_NAME} not found')
        current_config = request

        sink, sink_config = sink_config_from_dict(
            current_config.sink_config.name,
            current_config.sink_config.config
        )
        source, source_config = source_config_from_dict(
            current_config.source_config.name,
            current_config.source_config.config
        )

        scheduled_job = Schedule.add_job(
            func=process_scheduled_job,
            trigger='interval',
            seconds=request.time_in_seconds,
            id=JOB_NAME,
        )

        logger.info(current_config)

        return {"scheduled": True, "job_id": scheduled_job.id}


@app.get("/config", response_model=ApplicationConfig, response_model_exclude_unset=True, tags=["config"])
def classify_post():
    with rate_limiter.run():
        return current_config


@app.delete("/schedule/", tags=["schedule"])
async def remove_scheduled_job():
    global JOB_NAME
    global Schedule

    Schedule.remove_job(JOB_NAME)
    return {"scheduled": False, "job_id": JOB_NAME}


@app.post("/schedule/", tags=["schedule"])
async def add_scheduled_job():
    global JOB_NAME
    global Schedule
    global current_config

    if current_config:
        scheduled_job = Schedule.add_job(
            func=process_scheduled_job,
            trigger='interval',
            seconds=current_config.time_in_seconds,
            id=JOB_NAME,
        )
        return {"scheduled": True, "job_id": scheduled_job.id}
    else:
        return {"error": "No config exist"}


logger.info("Open http://127.0.0.1:8000/docs to see Swagger API Documentation.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
