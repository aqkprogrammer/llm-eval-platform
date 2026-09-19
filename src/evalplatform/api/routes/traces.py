from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from evalplatform.api.deps import ScorerDep, ServicesDep, SessionDep
from evalplatform.db.models import CaseResult, MetricScore, Trace
from evalplatform.schemas import (
    MetricScoreOut,
    Page,
    SpanOut,
    TraceIngest,
    TraceIngestResponse,
    TraceOut,
    TraceSummaryOut,
)
from evalplatform.services.monitoring import FLAG_METRICS, UnknownMetricError, ingest_trace

router = APIRouter(prefix="/api/traces", tags=["traces"])


def _summary(t: Trace, flagged: bool = False) -> TraceSummaryOut:
    return TraceSummaryOut(
        id=t.id,
        name=t.name,
        source=t.source,
        experiment_id=t.experiment_id,
        status=t.status,
        provider=t.provider,
        model=t.model,
        latency_ms=t.latency_ms,
        ttft_ms=t.ttft_ms,
        input_tokens=t.input_tokens,
        output_tokens=t.output_tokens,
        cost_usd=t.cost_usd,
        score_status=t.score_status,
        start_time=t.start_time,
        input_preview=(t.input or "")[:160],
        output_preview=(t.output or "")[:160],
        tags=t.tags or [],
        flagged=flagged,
    )


async def _ingest(
    payloads: list[TraceIngest], session: SessionDep, services: ServicesDep, scorer: ScorerDep
) -> list[TraceIngestResponse]:
    traces = []
    try:
        for p in payloads:
            traces.append(await ingest_trace(session, p, services.settings.monitoring_metrics))
        await session.commit()
    except UnknownMetricError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A trace with this id already exists"
        ) from exc
    for t in traces:
        if t.score_status == "pending":
            scorer.enqueue(t.id)
    return [TraceIngestResponse(id=t.id, score_status=t.score_status) for t in traces]


@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    payload: TraceIngest, session: SessionDep, services: ServicesDep, scorer: ScorerDep
) -> TraceIngestResponse:
    """Log a production LLM call; it is scored asynchronously by the requested metrics."""
    return (await _ingest([payload], session, services, scorer))[0]


@router.post(
    "/batch", response_model=list[TraceIngestResponse], status_code=status.HTTP_202_ACCEPTED
)
async def ingest_batch(
    payloads: list[TraceIngest], session: SessionDep, services: ServicesDep, scorer: ScorerDep
) -> list[TraceIngestResponse]:
    if len(payloads) > 500:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Max 500 traces per batch")
    return await _ingest(payloads, session, services, scorer)


@router.get("", response_model=Page[TraceSummaryOut])
async def list_traces(
    session: SessionDep,
    source: str | None = None,
    model: str | None = None,
    experiment_id: str | None = None,
    flagged: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TraceSummaryOut]:
    where = []
    if source:
        where.append(Trace.source == source)
    if model:
        where.append(Trace.model == model)
    if experiment_id:
        where.append(Trace.experiment_id == experiment_id)
    # "Flagged" = a failed safety/faithfulness check, the same definition the monitoring view uses.
    failed_ids = select(MetricScore.trace_id).where(
        MetricScore.passed.is_(False),
        MetricScore.trace_id.is_not(None),
        MetricScore.metric.in_(FLAG_METRICS),
    )
    if flagged is True:
        where.append(Trace.id.in_(failed_ids))
    elif flagged is False:
        where.append(Trace.id.not_in(failed_ids))
    total = await session.scalar(select(func.count()).select_from(Trace).where(*where)) or 0
    rows = (
        await session.scalars(
            select(Trace)
            .where(*where)
            .order_by(Trace.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    ids = [t.id for t in rows]
    flagged_ids = (
        set((await session.scalars(failed_ids.where(MetricScore.trace_id.in_(ids)))).all())
        if ids
        else set()
    )
    return Page[TraceSummaryOut](
        items=[_summary(t, t.id in flagged_ids) for t in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{trace_id}", response_model=TraceOut)
async def get_trace(trace_id: str, session: SessionDep) -> TraceOut:
    t = await session.get(
        Trace, trace_id, options=[selectinload(Trace.spans), selectinload(Trace.scores)]
    )
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trace not found")
    scores = list(t.scores)
    if not scores and t.source == "experiment":
        # Experiment scores are stored against the case result; surface them on its trace too.
        scores = list(
            (
                await session.scalars(
                    select(MetricScore)
                    .join(CaseResult, CaseResult.id == MetricScore.case_result_id)
                    .where(CaseResult.trace_id == t.id)
                )
            ).all()
        )
    summary = _summary(t, any(s.passed is False and s.metric in FLAG_METRICS for s in scores))
    return TraceOut(
        **summary.model_dump(),
        input=t.input,
        output=t.output,
        context=t.context or [],
        user_id=t.user_id,
        session_id=t.session_id,
        metadata_=t.metadata_ or {},
        end_time=t.end_time,
        spans=[SpanOut.model_validate(s) for s in sorted(t.spans, key=lambda s: s.start_time)],
        scores=[MetricScoreOut.model_validate(s) for s in sorted(scores, key=lambda s: s.metric)],
    )
