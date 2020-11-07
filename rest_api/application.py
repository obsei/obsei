import logging
import os
from contextlib import contextmanager
from threading import Semaphore
from typing import Any, Dict, List

import uvicorn as uvicorn
from fastapi import APIRouter
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

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


text_analyzer = TextAnalyzer(
    classifier_model_name="joeddav/bart-large-mnli-yahoo-answers",
    initialize_model=True,
)

CONCURRENT_REQUEST_PER_WORKER = int(os.getenv("CONCURRENT_REQUEST_PER_WORKER", 4))
rate_limiter = RequestLimiter(CONCURRENT_REQUEST_PER_WORKER)

router = APIRouter()


@router.post("/classifier", response_model=List[Dict[str, float]], response_model_exclude_unset=True)
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


def get_application() -> FastAPI:
    application = FastAPI(title="OBSEI-APIs", debug=True, version="0.1")

    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    application.add_exception_handler(HTTPException, http_error_handler)

    application.include_router(router)

    return application


app = get_application()

logger.info("Open http://127.0.0.1:8000/docs to see Swagger API Documentation.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
