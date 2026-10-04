"""``obsei serve``: webhook intake, MCP over streamable HTTP and a health check, in one process.

The store is opened once read-write and shared under a lock (DuckDB allows one writer).
"""

from __future__ import annotations

import dataclasses
import hmac
import json
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager

import anyio
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp

from obsei.config import ObseiConfig, build_pipeline
from obsei.core.context import Context
from obsei.mcp_server import create_server
from obsei.pipeline import Pipeline, PipelineError, SourceSpec, run
from obsei.sources.webhook import SignatureError, WebhookSource
from obsei.store import Store

MAX_BODY = 4 * 1024 * 1024
PUBLIC_PATHS = ("/healthz", "/ingest/")


class BearerAuth(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, token: str) -> None:
        super().__init__(app)
        self.expected = f"Bearer {token}"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith(PUBLIC_PATHS):
            return await call_next(request)
        given = request.headers.get("authorization", "")
        if not hmac.compare_digest(given, self.expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


class Intake:
    def __init__(self, config: ObseiConfig, ctx: Context, store: Store, lock: threading.Lock):
        self.store = store
        self.lock = lock
        self.routes: dict[tuple[str, str], tuple[Pipeline, WebhookSource]] = {}
        for spec in config.pipelines:
            if not any(s.type == "webhook" for s in spec.sources):
                continue
            pipeline = build_pipeline(config, spec.name, ctx)
            for source in pipeline.sources:
                if isinstance(source.source, WebhookSource):
                    only = dataclasses.replace(
                        pipeline, sources=[SourceSpec(source.key, source.source)]
                    )
                    self.routes[(spec.name, source.key)] = (only, source.source)

    def ingest(
        self, pipeline: str, key: str, body: bytes, headers: dict[str, str]
    ) -> dict[str, int]:
        route = self.routes.get((pipeline, key))
        if route is None:
            raise LookupError(f"no webhook source {pipeline}/{key}")
        built, source = route
        source.verify(body, headers)
        with self.lock:
            source.accept(json.loads(body))
            report = run(built, self.store)
        return {"received": report.fetched, "stored": report.stored}


def create_app(
    config: ObseiConfig, ctx: Context, store: Store, *, token: str | None, host: str = "127.0.0.1"
) -> Starlette:
    lock = threading.Lock()
    intake = Intake(config, ctx, store, lock)

    @contextmanager
    def shared_store() -> Iterator[Store]:
        with lock:
            yield store

    app = create_server(shared_store).streamable_http_app(streamable_http_path="/mcp", host=host)

    async def healthz(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def ingest(request: Request) -> Response:
        body = await request.body()
        if len(body) > MAX_BODY:
            return JSONResponse({"error": "payload too large"}, status_code=413)
        pipeline, key = request.path_params["pipeline"], request.path_params["source"]
        headers = {k.lower(): v for k, v in request.headers.items()}
        try:
            result = await anyio.to_thread.run_sync(intake.ingest, pipeline, key, body, headers)
        except LookupError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except SignatureError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        except PipelineError as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        return JSONResponse(result, status_code=202)

    app.router.routes.append(Route("/healthz", healthz, methods=["GET"]))
    app.router.routes.append(Route("/ingest/{pipeline}/{source}", ingest, methods=["POST"]))
    if token:
        app.add_middleware(BearerAuth, token=token)
    return app
