"""FastAPI application factory."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from evalplatform import __version__
from evalplatform.api.routes import (
    datasets,
    experiments,
    health,
    models,
    monitoring,
    prompts,
    traces,
)
from evalplatform.config import Settings, get_settings
from evalplatform.db.session import Database
from evalplatform.logging import configure_logging, get_logger
from evalplatform.providers.registry import ProviderRegistry
from evalplatform.services.context import AppServices
from evalplatform.services.jobs import JobManager
from evalplatform.services.monitoring import TraceScorer
from evalplatform.tracing.otel import build_tracer_provider
from evalplatform.tracing.tracer import Tracer, set_tracer

log = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings.database_url, settings.database_echo)
        if settings.auto_create_tables:
            await db.create_all()
        tracer = Tracer(build_tracer_provider(settings))
        set_tracer(tracer)
        services = AppServices(settings=settings, db=db, providers=ProviderRegistry(settings))
        jobs = JobManager(services)
        await jobs.recover()
        scorer = TraceScorer(services, settings.monitoring_workers)
        await scorer.start()
        app.state.services, app.state.jobs, app.state.scorer = services, jobs, scorer
        log.info("app.started", database=db.url.split("@")[-1], version=__version__)
        try:
            yield
        finally:
            await jobs.shutdown()
            await scorer.stop()
            tracer.shutdown()
            await services.aclose()
            log.info("app.stopped")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Evaluate and monitor LLM responses for accuracy, hallucination, latency, "
        "cost and safety across prompts and models.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def access_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        structlog.contextvars.bind_contextvars(path=request.url.path)
        try:
            response: Response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        if request.url.path.startswith("/api") and request.url.path != "/api/health":
            log.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
            )
        return response

    for router in (
        health.router,
        datasets.router,
        prompts.router,
        models.router,
        experiments.router,
        traces.router,
        monitoring.router,
    ):
        app.include_router(router)

    if settings.serve_frontend:
        _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA (local single-process mode). Docker uses nginx instead."""
    index = dist / "index.html"
    dist_root = dist.resolve()
    if not index.exists():
        return
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> Response:
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist_root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
