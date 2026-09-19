from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from evalplatform.api.deps import JobsDep, ServicesDep, SessionDep
from evalplatform.db.models import CaseResult, Dataset, Experiment, TestCase
from evalplatform.schemas import (
    CaseResultOut,
    ExperimentCreate,
    ExperimentOut,
    ExperimentSummaryOut,
    MetricScoreOut,
    Page,
)
from evalplatform.services.comparison import ComparisonError, compare_experiments
from evalplatform.services.experiments import ExperimentValidationError, create_experiment

router = APIRouter(prefix="/api", tags=["experiments"])


def _summary(exp: Experiment, dataset_name: str | None) -> dict[str, Any]:
    return {
        "id": exp.id,
        "name": exp.name,
        "description": exp.description,
        "dataset_id": exp.dataset_id,
        "dataset_name": dataset_name,
        "status": exp.status,
        "source": exp.source,
        "progress_total": exp.progress_total,
        "progress_done": exp.progress_done,
        "progress_failed": exp.progress_failed,
        "created_at": exp.created_at,
        "started_at": exp.started_at,
        "finished_at": exp.finished_at,
        "error": exp.error,
        "variant_count": len(exp.variants),
        "gate_passed": (exp.summary or {}).get("gate_passed"),
    }


async def _load(session: SessionDep, experiment_id: str) -> Experiment:
    exp = await session.get(
        Experiment,
        experiment_id,
        options=[selectinload(Experiment.variants)],
        populate_existing=True,
    )
    if exp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return exp


async def _detail(session: SessionDep, exp: Experiment) -> ExperimentOut:
    ds_name = await session.scalar(select(Dataset.name).where(Dataset.id == exp.dataset_id))
    return ExperimentOut.model_validate(
        {
            **_summary(exp, ds_name),
            "metrics": exp.metrics,
            "thresholds": exp.thresholds,
            "concurrency": exp.concurrency,
            "summary": exp.summary or {},
            "variants": exp.variants,
        }
    )


@router.get("/experiments", response_model=list[ExperimentSummaryOut])
async def list_experiments(
    session: SessionDep,
    status_: Annotated[str | None, Query(alias="status")] = None,
    dataset_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ExperimentSummaryOut]:
    stmt = (
        select(Experiment, Dataset.name)
        .join(Dataset, Dataset.id == Experiment.dataset_id)
        .options(selectinload(Experiment.variants))
        .order_by(Experiment.created_at.desc())
        .limit(limit)
    )
    if status_:
        stmt = stmt.where(Experiment.status == status_)
    if dataset_id:
        stmt = stmt.where(Experiment.dataset_id == dataset_id)
    rows = (await session.execute(stmt)).all()
    return [ExperimentSummaryOut.model_validate(_summary(e, n)) for e, n in rows]


@router.post("/experiments", response_model=ExperimentOut, status_code=status.HTTP_202_ACCEPTED)
async def start_experiment(
    payload: ExperimentCreate, session: SessionDep, services: ServicesDep, jobs: JobsDep
) -> ExperimentOut:
    try:
        exp = await create_experiment(
            session, payload, default_concurrency=services.settings.default_concurrency
        )
    except ExperimentValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    await session.commit()
    jobs.submit(exp.id)
    return await _detail(session, await _load(session, exp.id))


@router.get("/experiments/{experiment_id}", response_model=ExperimentOut)
async def get_experiment(experiment_id: str, session: SessionDep) -> ExperimentOut:
    return await _detail(session, await _load(session, experiment_id))


@router.get("/experiments/{experiment_id}/results", response_model=Page[CaseResultOut])
async def list_results(
    experiment_id: str,
    session: SessionDep,
    variant_id: str | None = None,
    passed: bool | None = None,
    test_case_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CaseResultOut]:
    await _load(session, experiment_id)
    where = [CaseResult.experiment_id == experiment_id]
    if variant_id:
        where.append(CaseResult.variant_id == variant_id)
    if passed is not None:
        where.append(CaseResult.passed.is_(passed))
    if test_case_id:
        where.append(CaseResult.test_case_id == test_case_id)
    total = await session.scalar(select(func.count()).select_from(CaseResult).where(*where)) or 0
    rows = (
        await session.execute(
            select(CaseResult, TestCase)
            .join(TestCase, TestCase.id == CaseResult.test_case_id)
            .where(*where)
            .options(selectinload(CaseResult.scores))
            .order_by(TestCase.position, CaseResult.variant_id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    items = [
        CaseResultOut(
            id=r.id,
            variant_id=r.variant_id,
            test_case_id=r.test_case_id,
            input=tc.input,
            expected_output=tc.expected_output,
            context=tc.context or [],
            tags=tc.tags or [],
            rendered_prompt=r.rendered_prompt,
            output=r.output,
            error=r.error,
            latency_ms=r.latency_ms,
            ttft_ms=r.ttft_ms,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            cost_usd=r.cost_usd,
            passed=r.passed,
            trace_id=r.trace_id,
            scores=[
                MetricScoreOut.model_validate(s) for s in sorted(r.scores, key=lambda s: s.metric)
            ],
        )
        for r, tc in rows
    ]
    return Page[CaseResultOut](items=items, total=total, limit=limit, offset=offset)


@router.post("/experiments/{experiment_id}/cancel", response_model=ExperimentOut)
async def cancel_experiment(
    experiment_id: str, session: SessionDep, jobs: JobsDep
) -> ExperimentOut:
    exp = await _load(session, experiment_id)
    if exp.status not in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Experiment is already {exp.status}")
    await jobs.cancel(experiment_id)
    return await _detail(session, await _load(session, experiment_id))


@router.delete("/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(experiment_id: str, session: SessionDep, jobs: JobsDep) -> None:
    exp = await _load(session, experiment_id)
    if jobs.is_running(experiment_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cancel the experiment before deleting it")
    await session.delete(exp)
    await session.commit()


@router.get("/compare")
async def compare(
    session: SessionDep,
    baseline: str,
    candidate: str,
    baseline_variant: str | None = None,
    candidate_variant: str | None = None,
    tolerance: Annotated[float, Query(ge=0, le=1)] = 0.02,
) -> dict[str, Any]:
    try:
        return await compare_experiments(
            session, baseline, candidate, baseline_variant, candidate_variant, tolerance
        )
    except ComparisonError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/leaderboard")
async def leaderboard(session: SessionDep, dataset_id: str | None = None) -> dict[str, Any]:
    """Latest result per (dataset, prompt version, model) across completed experiments."""
    stmt = (
        select(Experiment, Dataset.name)
        .join(Dataset, Dataset.id == Experiment.dataset_id)
        .where(Experiment.status == "completed")
        .order_by(Experiment.finished_at.desc())
    )
    if dataset_id:
        stmt = stmt.where(Experiment.dataset_id == dataset_id)
    seen: set[tuple[str, str, Any, str]] = set()
    rows: list[dict[str, Any]] = []
    for exp, ds_name in (await session.execute(stmt)).all():
        for v in (exp.summary or {}).get("variants", []):
            key = (
                exp.dataset_id,
                str(v.get("prompt")),
                v.get("prompt_version"),
                str(v.get("model_config_name")),
            )
            if key in seen:
                continue
            seen.add(key)
            metrics = v.get("metrics", {})
            rows.append(
                {
                    "dataset_id": exp.dataset_id,
                    "dataset_name": ds_name,
                    "experiment_id": exp.id,
                    "experiment_name": exp.name,
                    "variant_id": v.get("variant_id"),
                    "label": v.get("label"),
                    "model": v.get("model"),
                    "model_config_name": v.get("model_config_name"),
                    "provider": v.get("provider"),
                    "prompt": v.get("prompt"),
                    "prompt_version": v.get("prompt_version"),
                    "composite_score": v.get("composite_score"),
                    "pass_rate": v.get("pass_rate"),
                    "total_cost_usd": v.get("total_cost_usd"),
                    "cases": v.get("cases"),
                    "metrics": {k: m.get("mean") for k, m in metrics.items()},
                    "latency_p95": (metrics.get("latency_ms") or {}).get("p95"),
                    "finished_at": exp.finished_at.isoformat() if exp.finished_at else None,
                }
            )
    rows.sort(key=lambda r: (r["composite_score"] is None, -(r["composite_score"] or 0)))
    return {"rows": rows}
