from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from evalplatform.api.deps import SessionDep
from evalplatform.services.monitoring import monitoring_overview

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/overview")
async def overview(
    session: SessionDep,
    window: Annotated[str, Query(pattern=r"^\d{1,4}[mhd]$")] = "24h",
    buckets: Annotated[int, Query(ge=2, le=200)] = 24,
    model: str | None = None,
) -> dict[str, Any]:
    """Time-bucketed quality, latency, cost and volume for production traces."""
    return await monitoring_overview(session, window, buckets, model)
