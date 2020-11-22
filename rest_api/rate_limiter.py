from contextlib import contextmanager
from threading import Semaphore

from fastapi import HTTPException


class RequestLimiter:
    def __init__(self, concurrent_request_per_worker: int = 1):
        self.semaphore = Semaphore(concurrent_request_per_worker - 1)

    @contextmanager
    def run(self):
        acquired = self.semaphore.acquire(blocking=False)
        if not acquired:
            raise HTTPException(status_code=503, detail="The server is busy processing requests.")
        try:
            yield acquired
        finally:
            self.semaphore.release()