"""``obsei serve``: webhook intake, scheduled pipelines, MCP over streamable HTTP, the read-only
Studio and its API, an optional Slack command, and a health check, in one process.

The store is opened once read-write and shared under a lock (DuckDB allows one writer).
"""

from __future__ import annotations

import dataclasses
import json
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager

import anyio
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from obsei import slackbot, studio
from obsei.access import AUDITED, RANK, Authenticator, Principal, Role, required_role
from obsei.ask import ask
from obsei.config import ObseiConfig, build_pipeline
from obsei.core.context import Context
from obsei.llm.client import LlmError
from obsei.mcp_server import create_server
from obsei.pipeline import Pipeline, PipelineError, SourceSpec, run
from obsei.runner import Scheduler
from obsei.sources.webhook import SignatureError, WebhookSource
from obsei.store import Store

MAX_BODY = 4 * 1024 * 1024
SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        b"connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
)


AuditHook = Callable[[Principal, str], Awaitable[None]]


class AccessControl(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, authenticator: Authenticator, audit: AuditHook) -> None:
        super().__init__(app)
        self.auth = authenticator
        self.audit = audit

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        needed = required_role(request.url.path)
        if needed is None:
            return await call_next(request)
        principal = self.auth.resolve({k.lower(): v for k, v in request.headers.items()})
        if principal is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if RANK[principal.role] < RANK[needed]:
            return JSONResponse({"error": f"needs the {needed} role"}, status_code=403)
        if needed in AUDITED:
            await self.audit(principal, request.url.path)
        request.state.principal = principal
        return await call_next(request)


class SecurityHeaders:
    """Adds a strict CSP and anti-sniffing/framing headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend(h for h in SECURITY_HEADERS if h[0] not in present)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, with_headers)


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


class Handlers:
    def __init__(self, config: ObseiConfig, ctx: Context, store: Store) -> None:
        self.config = config
        self.ctx = ctx
        self.store = store
        self.lock = threading.Lock()
        self.intake = Intake(config, ctx, store, self.lock)
        self.k = config.themes.k_anonymity
        self.scheduler = Scheduler(config, ctx, self.shared_store)

    @contextmanager
    def shared_store(self) -> Iterator[Store]:
        with self.lock:
            yield self.store

    def answer(self, question: str) -> str:
        with self.shared_store() as s:
            result = ask(
                s,
                question,
                self.ctx.chat(self.config.ask_llm),
                embedder=self.ctx.embedder(self.config.themes.embedder),
                k_anonymity=self.k,
            )
        cited = ", ".join(result.citations)
        return result.text + (f"\n\n_sources: {cited}_" if cited else "")

    async def healthz(self, request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def ingest(self, request: Request) -> Response:
        body = await request.body()
        if len(body) > MAX_BODY:
            return JSONResponse({"error": "payload too large"}, status_code=413)
        pipeline, key = request.path_params["pipeline"], request.path_params["source"]
        headers = {k.lower(): v for k, v in request.headers.items()}
        try:
            result = await anyio.to_thread.run_sync(
                self.intake.ingest, pipeline, key, body, headers
            )
        except LookupError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except SignatureError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        except PipelineError as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        return JSONResponse(result, status_code=202)

    def _snapshot(self, role: Role | None) -> str:
        with self.shared_store() as s:
            snap = studio.snapshot(s, k=self.k, evidence_per_theme=0)
        return snap.model_copy(update={"role": role}).model_dump_json()

    async def api_snapshot(self, request: Request) -> Response:
        principal: Principal | None = getattr(request.state, "principal", None)
        role = principal.role if principal else None
        body = await anyio.to_thread.run_sync(self._snapshot, role)
        return Response(body, media_type="application/json")

    def _theme(self, theme_id: str) -> str:
        with self.shared_store() as s:
            items = studio.theme_evidence(s, theme_id, k=self.k)
        return "[" + ",".join(e.model_dump_json() for e in items) + "]"

    async def api_theme(self, request: Request) -> Response:
        body = await anyio.to_thread.run_sync(self._theme, request.path_params["theme"])
        return Response(body, media_type="application/json")

    async def api_runs(self, request: Request) -> Response:
        runs = {
            name: {
                "started_at": o.started_at.isoformat(),
                "ok": o.ok,
                "summary": o.summary(),
            }
            for name, o in self.scheduler.last.items()
        }
        return JSONResponse({"scheduled": self.scheduler.scheduled(), "last": runs})

    async def api_ask(self, request: Request) -> Response:
        question = str((await request.json()).get("question", "")).strip()
        if not question:
            return JSONResponse({"error": "question is required"}, status_code=400)
        try:
            text = await anyio.to_thread.run_sync(self.answer, question)
        except (KeyError, LlmError, OSError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        return JSONResponse({"answer": text})

    def _reply_to_slack(self, question: str, response_url: str) -> None:
        try:
            text = self.answer(question)
        except (KeyError, LlmError, OSError) as exc:
            text = f"Sorry, I could not answer: {exc}"
        self.ctx.http.post(response_url, json={"response_type": "in_channel", "text": text})

    async def slack(self, request: Request) -> Response:
        secret = slackbot.signing_secret()
        if secret is None:
            return JSONResponse({"error": "slack is not configured"}, status_code=404)
        body = await request.body()
        try:
            slackbot.verify(
                secret,
                body,
                request.headers.get("x-slack-request-timestamp", ""),
                request.headers.get("x-slack-signature", ""),
            )
        except slackbot.SlackSignatureError as exc:
            return JSONResponse({"error": str(exc)}, status_code=401)
        question, response_url = slackbot.command(body)
        if not question or not slackbot.is_slack_url(response_url):
            return JSONResponse({"response_type": "ephemeral", "text": "Usage: /obsei <question>"})
        self.ctx.egress.check(response_url)
        task = BackgroundTask(
            anyio.to_thread.run_sync, self._reply_to_slack, question, response_url
        )
        return JSONResponse(
            {"response_type": "ephemeral", "text": "Looking through feedback…"}, background=task
        )


def create_app(
    config: ObseiConfig, ctx: Context, store: Store, *, token: str | None, host: str = "127.0.0.1"
) -> Starlette:
    h = Handlers(config, ctx, store)
    app = create_server(h.shared_store, k_anonymity=h.k).streamable_http_app(
        streamable_http_path="/mcp", host=host
    )
    app.router.routes.extend(
        [
            Route("/healthz", h.healthz, methods=["GET"]),
            Route("/ingest/{pipeline}/{source}", h.ingest, methods=["POST"]),
            Route("/api/snapshot", h.api_snapshot, methods=["GET"]),
            Route("/api/themes/{theme}", h.api_theme, methods=["GET"]),
            Route("/api/ask", h.api_ask, methods=["POST"]),
            Route("/api/runs", h.api_runs, methods=["GET"]),
            Route("/slack/commands", h.slack, methods=["POST"]),
            Mount("/studio", StaticFiles(directory=studio.static_dir(), html=True), name="studio"),
        ]
    )
    auth = Authenticator(config.access, token)
    if auth.enabled:

        async def audit(principal: Principal, path: str) -> None:
            def write() -> None:
                with h.shared_store() as s:
                    s.audit(
                        "access", {"user": principal.name, "role": principal.role, "path": path}
                    )

            await anyio.to_thread.run_sync(write)

        app.add_middleware(AccessControl, authenticator=auth, audit=audit)
    app.add_middleware(SecurityHeaders)
    app.state.scheduler = h.scheduler
    return app
