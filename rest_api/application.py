import logging
from typing import List
from uuid import uuid4

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.base import BaseScheduler
from fastapi import HTTPException
from hydra.experimental import compose, initialize
from hydra.utils import instantiate
from omegaconf import DictConfig, OmegaConf

from obsei.processor import Processor
from obsei.text_analyzer import AnalyzerRequest, TextAnalyzer
from rest_api.api_request_response import ScheduleResponse, TaskAddResponse, TaskConfig, ClassifierRequest, \
    ClassifierResponse, TaskDetail
from rest_api.global_utils import get_application, sink_map, source_map
from rest_api.rate_limiter import RequestLimiter
from rest_api.task_config_store import TaskConfigStore

logger = logging.getLogger(__name__)

config_store: TaskConfigStore
app_cfg: DictConfig
scheduler: BaseScheduler
text_analyzer: TextAnalyzer
processor: Processor
rate_limiter: RequestLimiter


app = get_application()


def process_scheduled_job(task_config: TaskConfig):
    try:
        if task_config:
            processor.process(
                sink=sink_map[task_config.sink_config.TYPE],
                sink_config=task_config.sink_config,
                source=source_map[task_config.source_config.TYPE],
                source_config=task_config.source_config,
                analyzer_config=task_config.analyzer_config
            )
    except Exception as ex:
        logger.error(f'Exception occur: {ex}')


def schedule_tasks():
    tasks = config_store.get_all_tasks()
    jobs = []
    for task in tasks:
        jobs.append(
            scheduler.add_job(
                func=process_scheduled_job,
                kwargs={
                    "task_config": task.config
                },
                trigger='interval',
                seconds=task.config.time_in_seconds,
                id=task.id,
            )
        )


def scheduler_init():
    global scheduler

    try:
        #job_store = instantiate(app_cfg.task_scheduler.jobstore)
        scheduler = instantiate(app_cfg.task_scheduler, _recursive_=True)
        #scheduler.configure({'default': job_store})

        scheduler.start()
        logger.info("Created Schedule Object")
        schedule_tasks()
    except Exception as ex:
        logger.error(f'Unable to Create Schedule Object, error: {ex.__cause__}')
        raise ex


def logging_init():
    logging.basicConfig(**app_cfg.logging.base_config)

    # logging.getLogger("obsei").setLevel(app_cfg.logging.base_config.level)
    # logging.getLogger("uvicorn").setLevel(app_cfg.logging.base_config.level)
    logging.root.setLevel(app_cfg.logging.base_config.level)
    logging.root.propagate = True

    gunicorn_logger = logging.getLogger('gunicorn.error')
    gunicorn_logger.setLevel(app_cfg.logging.base_config.level)
    gunicorn_logger.propagate = True


def init_config_store():
    global config_store
    config_store = instantiate(app_cfg.task_config_store, _recursive_=True)


def init_analyzer():
    global text_analyzer
    text_analyzer = instantiate(app_cfg.analyzer, _recursive_=True)


def init_processor():
    global processor
    processor = Processor(text_analyzer)


def init_rate_limiter():
    global rate_limiter
    rate_limiter = instantiate(app_cfg.rate_limiter, _recursive_=True)


def config_init() -> None:
    global app_cfg
    with initialize(config_path="../config"):
        cfg = compose("rest.yaml")
        logger.debug("Configuration: \n" + OmegaConf.to_yaml(cfg))
        app_cfg = cfg


@app.on_event("startup")
def app_init():
    config_init()
    logging_init()
    init_analyzer()
    init_processor()
    init_config_store()
    scheduler_init()
    init_rate_limiter()

    logger.info("Open http://127.0.0.1:9898/redoc or http://127.0.0.1:9898/docs to see API Documentation.")


@app.get(
    "/tasks/schedules/",
    response_model=List[ScheduleResponse],
    response_model_exclude_unset=True,
    tags=["task"]
)
async def get_scheduled_syncs():
    with rate_limiter.run():
        schedules = []
        for job in scheduler.get_jobs():
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
    with rate_limiter.run():
        return config_store.get_all_tasks()


@app.get(
    "/tasks/{task_id}",
    response_model=TaskDetail,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def get_task(task_id: str):
    with rate_limiter.run():
        return config_store.get_task_by_id(task_id)


@app.delete(
    "/tasks/{task_id}",
    response_model=TaskAddResponse,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def delete_task(task_id: str):
    with rate_limiter.run():
        try:
            scheduler.remove_job(job_id=task_id)
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

        return TaskAddResponse(id=task_id)


@app.post(
    "/tasks/{task_id}",
    response_model=TaskAddResponse,
    response_model_exclude_unset=True,
    tags=["task"]
)
async def update_task(task_id: str, request: TaskConfig):
    with rate_limiter.run():
        try:
            scheduler.remove_job(job_id=task_id)
        except JobLookupError as ex:
            logger.warning(f'Job {task_id} not found. Error: {ex.__cause__}')

        task_detail = TaskDetail(id=task_id, config=request)
        config_store.update_task(task_detail)
        scheduler.add_job(
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
    with rate_limiter.run():
        task_detail = TaskDetail(id=str(uuid4()), config=request)
        config_store.add_task(task_detail)
        scheduler.add_job(
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
            analyzer_config=request.analyzer_config,
        )

        response = []
        for analyzer_response in analyzer_responses:
            response.append(analyzer_response.classification)

        return ClassifierResponse(data=response)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9898)
