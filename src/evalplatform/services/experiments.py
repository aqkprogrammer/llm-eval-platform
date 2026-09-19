"""Experiment creation and matrix expansion (shared by the API and the CLI)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from evalplatform.db.models import (
    Dataset,
    Experiment,
    ExperimentVariant,
    ModelConfig,
    PromptVersion,
    TestCase,
)
from evalplatform.metrics.registry import DEFAULT_METRICS, get_metric_class, normalize_spec
from evalplatform.schemas import ExperimentCreate
from evalplatform.services.stats import normalize_thresholds


class ExperimentValidationError(ValueError):
    pass


def model_snapshot(mc: ModelConfig) -> dict[str, Any]:
    return {
        "id": mc.id,
        "name": mc.name,
        "provider": mc.provider,
        "model": mc.model,
        "temperature": mc.temperature,
        "max_tokens": mc.max_tokens,
        "params": mc.params or {},
    }


def prompt_snapshot(pv: PromptVersion) -> dict[str, Any]:
    return {
        "id": pv.id,
        "template_id": pv.template_id,
        "name": pv.template.name,
        "version": pv.version,
        "system_prompt": pv.system_prompt,
        "user_template": pv.user_template,
    }


def resolve_metric_specs(metrics: list[Any] | None) -> list[dict[str, Any]]:
    raw = metrics if metrics else DEFAULT_METRICS
    specs: list[dict[str, Any]] = []
    for m in raw:
        spec = normalize_spec(m.model_dump() if hasattr(m, "model_dump") else m)
        try:
            cls = get_metric_class(spec["name"])
        except KeyError as exc:
            raise ExperimentValidationError(str(exc.args[0])) from exc
        if not cls.is_available():
            raise ExperimentValidationError(
                f"Metric '{cls.name}' needs the optional '{cls.backend}' extra"
            )
        specs.append(spec)
    names = [s["name"] for s in specs]
    if len(names) != len(set(names)):
        raise ExperimentValidationError("Duplicate metrics in experiment")
    return specs


async def create_experiment(
    session: AsyncSession,
    payload: ExperimentCreate,
    *,
    default_concurrency: int,
    source: str = "api",
) -> Experiment:
    dataset = await session.get(Dataset, payload.dataset_id)
    if dataset is None:
        raise ExperimentValidationError(f"Dataset '{payload.dataset_id}' not found")
    case_count = await session.scalar(
        select(func.count()).select_from(TestCase).where(TestCase.dataset_id == dataset.id)
    )
    if not case_count:
        raise ExperimentValidationError("Dataset has no test cases")

    versions = (
        await session.scalars(
            select(PromptVersion)
            .where(PromptVersion.id.in_(payload.prompt_version_ids))
            .options(selectinload(PromptVersion.template))
        )
    ).all()
    missing = set(payload.prompt_version_ids) - {v.id for v in versions}
    if missing:
        raise ExperimentValidationError(f"Prompt versions not found: {', '.join(sorted(missing))}")
    models = (
        await session.scalars(
            select(ModelConfig).where(ModelConfig.id.in_(payload.model_config_ids))
        )
    ).all()
    missing = set(payload.model_config_ids) - {m.id for m in models}
    if missing:
        raise ExperimentValidationError(f"Model configs not found: {', '.join(sorted(missing))}")

    specs = resolve_metric_specs(payload.metrics)
    try:
        normalize_thresholds(payload.thresholds)
    except ValueError as exc:
        raise ExperimentValidationError(str(exc)) from exc

    exp = Experiment(
        name=payload.name,
        description=payload.description,
        dataset_id=dataset.id,
        status="queued",
        metrics=specs,
        thresholds=dict(payload.thresholds),
        concurrency=payload.concurrency or default_concurrency,
        case_limit=payload.case_limit,
        source=source,
    )
    order = {vid: i for i, vid in enumerate(payload.prompt_version_ids)}
    morder = {mid: i for i, mid in enumerate(payload.model_config_ids)}
    for pv in sorted(versions, key=lambda v: order[v.id]):
        for mc in sorted(models, key=lambda m: morder[m.id]):
            exp.variants.append(
                ExperimentVariant(
                    label=f"{pv.template.name} v{pv.version} · {mc.name}",
                    prompt_version_id=pv.id,
                    model_config_id=mc.id,
                    prompt_snapshot=prompt_snapshot(pv),
                    model_snapshot=model_snapshot(mc),
                )
            )
    limit = min(case_count, payload.case_limit) if payload.case_limit else case_count
    exp.progress_total = limit * len(exp.variants)
    session.add(exp)
    await session.flush()
    return exp
