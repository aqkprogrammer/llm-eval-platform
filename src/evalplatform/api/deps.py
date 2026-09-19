"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from evalplatform.services.context import AppServices
from evalplatform.services.jobs import JobManager
from evalplatform.services.monitoring import TraceScorer


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def get_scorer(request: Request) -> TraceScorer:
    return request.app.state.scorer


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.services.db.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
ServicesDep = Annotated[AppServices, Depends(get_services)]
JobsDep = Annotated[JobManager, Depends(get_jobs)]
ScorerDep = Annotated[TraceScorer, Depends(get_scorer)]
