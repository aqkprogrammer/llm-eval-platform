"""YAML run configuration used by ``evalctl run`` (CI gating)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from evalplatform.db.models import Dataset, PromptTemplate, PromptVersion
from evalplatform.schemas import ExperimentCreate, MetricSpec, ProviderName
from evalplatform.services.datasets import CaseIn, detect_format, parse_cases
from evalplatform.services.seed import upsert_dataset, upsert_model_config, upsert_prompt_version


class RunConfigError(ValueError):
    pass


class DatasetRef(BaseModel):
    path: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _one(self) -> DatasetRef:
        if not self.path and not self.name:
            raise ValueError("dataset needs 'path' or 'name'")
        return self


class PromptRef(BaseModel):
    name: str
    version: int | None = None
    system: str | None = None
    template: str | None = None


class ModelRef(BaseModel):
    name: str | None = None
    provider: ProviderName = "mock"
    model: str
    temperature: float | None = 0.0
    max_tokens: int = 512
    params: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    name: str = "ci-eval"
    description: str = ""
    dataset: DatasetRef
    prompts: list[PromptRef] = Field(min_length=1)
    models: list[ModelRef] = Field(min_length=1)
    metrics: list[str | MetricSpec] | None = None
    thresholds: dict[str, float | dict[str, float]] = Field(default_factory=dict)
    concurrency: int | None = None
    case_limit: int | None = None


def load_run_config(path: Path) -> tuple[RunConfig, Path]:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise RunConfigError(f"Cannot read config {path}: {exc}") from exc
    try:
        return RunConfig.model_validate(data or {}), path.parent
    except Exception as exc:
        raise RunConfigError(f"Invalid config {path}: {exc}") from exc


def _fingerprint(items: list[tuple[str, str | None, list[str], list[str]]]) -> str:
    return hashlib.sha256(repr(items).encode()).hexdigest()


async def _matching_dataset(
    session: AsyncSession, name: str, cases: list[CaseIn]
) -> Dataset | None:
    """Reuse a stored dataset with this name when it holds exactly the same cases."""
    dataset = await session.scalar(
        select(Dataset).where(Dataset.name == name).options(selectinload(Dataset.cases))
    )
    if dataset is None:
        return None
    stored = [(c.input, c.expected_output, list(c.context), list(c.tags)) for c in dataset.cases]
    incoming = [(c.input, c.expected_output, c.context, c.tags) for c in cases]
    return dataset if _fingerprint(stored) == _fingerprint(incoming) else None


async def materialize(session: AsyncSession, cfg: RunConfig, base_dir: Path) -> ExperimentCreate:
    """Create/reuse the dataset, prompt versions and model configs a config refers to."""
    if cfg.dataset.path:
        path = Path(cfg.dataset.path)
        if not path.is_absolute():
            path = (base_dir / path) if (base_dir / path).exists() else path
        if not path.exists():
            raise RunConfigError(f"Dataset file not found: {cfg.dataset.path}")
        content = path.read_bytes()
        cases = parse_cases(content, detect_format(path.name))
        dataset = (
            await _matching_dataset(session, cfg.dataset.name, cases) if cfg.dataset.name else None
        )
        if dataset is None:
            # Content-addressed name: editing the file creates a new dataset instead of silently
            # mixing results from different case sets.
            digest = hashlib.sha256(content).hexdigest()[:8]
            name = f"{cfg.dataset.name or path.stem}@{digest}"
            dataset, _ = await upsert_dataset(session, name, cases, f"Imported from {path.name}")
    else:
        dataset = await session.scalar(select(Dataset).where(Dataset.name == cfg.dataset.name))
        if dataset is None:
            raise RunConfigError(f"Dataset '{cfg.dataset.name}' not found")

    version_ids: list[str] = []
    for p in cfg.prompts:
        if p.template is not None:
            pv = await upsert_prompt_version(session, p.name, p.system or "", p.template)
        else:
            template = await session.scalar(
                select(PromptTemplate)
                .where(PromptTemplate.name == p.name)
                .options(selectinload(PromptTemplate.versions))
                .execution_options(populate_existing=True)
            )
            if template is None or not template.versions:
                raise RunConfigError(
                    f"Prompt '{p.name}' not found (give 'template' to define it inline)"
                )
            matches: list[PromptVersion] = [
                v for v in template.versions if p.version is None or v.version == p.version
            ]
            if not matches:
                raise RunConfigError(f"Prompt '{p.name}' has no version {p.version}")
            pv = matches[-1]
        version_ids.append(pv.id)

    model_ids: list[str] = []
    for m in cfg.models:
        spec = m.model_dump()
        spec["name"] = m.name or (m.model if m.provider == "mock" else f"{m.provider}:{m.model}")
        mc = await upsert_model_config(session, spec)
        model_ids.append(mc.id)
    await session.flush()
    return ExperimentCreate(
        name=cfg.name,
        description=cfg.description,
        dataset_id=dataset.id,
        prompt_version_ids=version_ids,
        model_config_ids=model_ids,
        metrics=cfg.metrics,
        thresholds=cfg.thresholds,
        concurrency=cfg.concurrency,
        case_limit=cfg.case_limit,
    )
