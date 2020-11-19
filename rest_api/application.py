import logging
import os
from typing import List
from uuid import uuid4

import uvicorn as uvicorn
from apscheduler.jobstores.base import JobLookupError
from fastapi import HTTPException

from obsei.sink.sink_utils import sink_map
from obsei.source.source_utils import source_map
from obsei.text_analyzer import AnalyzerRequest
from rest_api.api_request_response import ScheduleResponse, TaskAddResponse, TaskConfig, ClassifierRequest, \
    ClassifierResponse, \
    TaskDetail
from rest_api.global_utils import get_application, processor, rate_limiter, schedule, text_analyzer
from rest_api.task_config_store import TaskConfigStore


log_level = os.environ.get('LOG_LEVEL', logging.DEBUG)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p"
)

logger = logging.getLogger(__name__)
logging.getLogger("obsei").setLevel(log_level)
logging.root.setLevel(log_level)
logging.root.propagate = True

gunicorn_logger = logging.getLogger('gunicorn.error')
gunicorn_logger.setLevel(log_level)
gunicorn_logger.propagate = True

config_store: TaskConfigStore

app = get_application()


def process_scheduled_job(task_config: TaskConfig):
    try:
        if task_config:
            processor.process(
                sink=sink_map[task_config.sink_config.name],
                sink_config=task_config.sink_config,
                source=source_map[task_config.source_config.name],
                source_config=task_config.source_config,
            )
    except Exception as ex:
        logger.error(f'Exception occur: {ex}')


def start_scheduler():
    try:
        schedule.start()
        logger.info("Created Schedule Object")
    except Exception as ex:
        logger.error(f'Unable to Create Schedule Object, error: {ex.__cause__ }')
        raise ex


def init_config_store():
    global config_store
    config_store = TaskConfigStore()


def schedule_tasks():
    global config_store
    tasks = config_store.get_all_tasks()
    jobs = []
    for task in tasks:
        jobs.append(
            schedule.add_job(
                func=process_scheduled_job,
                kwargs={
                    "task_config": task.config
                },
                trigger='interval',
                seconds=task.config.time_in_seconds,
                id=task.id,
            )
        )


@app.on_event("startup")
async def load_schedule_or_create_blank():
    init_config_store()
    start_scheduler()
    schedule_tasks()


@app.get(
    "/tasks/schedules/",
    response_model=List[ScheduleResponse],
    response_model_exclude_unset=True,
    tags=["task"]
)
async def get_scheduled_syncs():
    with rate_limiter.run():
        schedules = []
        for job in schedule.get_jobs():
            schedules.append(
                ScheduleResponse(
                    id=str(job.id),
                    run_frequency=str(job.trigger),
                    next_run=str(job.next_run_time)
                )
            )
        return schedules


@app.get(
    "/tasks/",
    response_model=List[TaskDetail],
    response_model_exclude_unset=True,
    tags=["task"]
)
async def get_all_tasks():
    global config_store
    with rate_limiter.run():
        return config_store.get_all_tasks()


@app.get(
    "/tasks/{task_id}",
    response_model=TaskDetail,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def get_task(task_id: str):
    global config_store
    with rate_limiter.run():
        return config_store.get_task_by_id(task_id)


@app.delete(
    "/tasks/{task_id}",
    response_model=str,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def delete_task(task_id: str):
    global config_store
    with rate_limiter.run():
        try:
            schedule.remove_job(job_id=task_id)
        except JobLookupError as ex:
            logger.warning(f'Job {task_id} not found. Error: {ex.__cause__}')

        try:
            config_store.delete_task(task_id)
        except Exception as ex:
            logger.warning(f'Task {task_id} not able to delete. Error: {ex.__cause__}')
            raise HTTPException(
                status_code=404,
                detail=f'Task {task_id} not found'
            )

        return task_id


@app.post(
    "/tasks/{task_id}",
    response_model=TaskAddResponse,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def update_task(task_id: str, request: TaskConfig):
    global config_store

    with rate_limiter.run():
        try:
            schedule.remove_job(job_id=task_id)
        except JobLookupError as ex:
            logger.warning(f'Job {task_id} not found. Error: {ex.__cause__}')

        task_detail = TaskDetail(id=task_id, config=request)
        config_store.update_task(task_detail)
        schedule.add_job(
            func=process_scheduled_job,
            kwargs={
                "task_config": task_detail.config
            },
            trigger='interval',
            seconds=task_detail.config.time_in_seconds,
            id=task_detail.id,
        )

        return TaskAddResponse(id=task_detail.id)


@app.post(
    "/tasks/",
    response_model=TaskAddResponse,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def add_task(request: TaskConfig):
    global config_store

    with rate_limiter.run():
        task_detail = TaskDetail(id=str(uuid4()), config=request)
        config_store.add_task(task_detail)
        schedule.add_job(
            func=process_scheduled_job,
            kwargs={
                "task_config": task_detail.config
            },
            trigger='interval',
            seconds=task_detail.config.time_in_seconds,
            id=task_detail.id,
        )

        return TaskAddResponse(id=task_detail.id)


@app.post(
    "/classifier",
    response_model=ClassifierResponse,
    response_model_exclude_unset=True,
    tags=["api"]
)
def classify_texts(request: ClassifierRequest):
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


logger.info("Open http://127.0.0.1:9898/redoc to see API Documentation.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9898)
