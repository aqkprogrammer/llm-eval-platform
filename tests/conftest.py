from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from evalplatform.api.app import create_app
from evalplatform.config import Settings
from evalplatform.db.session import Database
from evalplatform.metrics.base import MetricContext
from evalplatform.providers.registry import ProviderRegistry
from evalplatform.services.context import AppServices


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        mock_latency_scale=0.0,
        serve_frontend=False,
        otel_exporter="none",
        log_level="WARNING",
        default_concurrency=8,
    )


@pytest.fixture
async def services(settings: Settings) -> AsyncIterator[AppServices]:
    db = Database(settings.database_url)
    await db.create_all()
    svc = AppServices(settings=settings, db=db, providers=ProviderRegistry(settings))
    yield svc
    await svc.aclose()


@pytest.fixture
def metric_ctx(settings: Settings) -> MetricContext:
    return MetricContext(providers=ProviderRegistry(settings))


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seeded(app: FastAPI) -> AppServices:
    from evalplatform.services.seed import seed_catalog

    services: AppServices = app.state.services
    await seed_catalog(services)
    return services


@pytest.fixture(autouse=True)
def _fast_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every code path (including CLI commands that read env settings) offline and fast."""
    from evalplatform.config import reset_settings_cache

    monkeypatch.setenv("MOCK_LATENCY_SCALE", "0")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
