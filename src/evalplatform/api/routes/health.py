from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select, text

from evalplatform import __version__
from evalplatform.api.deps import ServicesDep, SessionDep
from evalplatform.db.models import Dataset, Experiment, ModelConfig, PromptTemplate, Trace
from evalplatform.metrics.registry import all_metric_classes

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health(session: SessionDep, services: ServicesDep) -> dict[str, Any]:
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    s = services.settings
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "database": {"ok": db_ok, "dialect": "sqlite" if s.is_sqlite else "postgresql"},
        "providers": services.providers.status(),
        "judge": {"provider": s.judge_provider, "model": s.judge_model},
        "tracing": {"otel_exporter": s.otel_exporter, "langfuse": s.langfuse_enabled},
    }


@router.get("/metrics")
async def list_metrics() -> list[dict[str, Any]]:
    return [cls.info() for cls in all_metric_classes()]


@router.get("/stats")
async def stats(session: SessionDep) -> dict[str, Any]:
    async def count(model: Any, *where: Any) -> int:
        return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    return {
        "datasets": await count(Dataset),
        "prompts": await count(PromptTemplate),
        "models": await count(ModelConfig),
        "experiments": await count(Experiment),
        "experiments_running": await count(
            Experiment, Experiment.status.in_(["queued", "running"])
        ),
        "traces_production": await count(Trace, Trace.source == "production"),
        "traces_total": await count(Trace),
    }
