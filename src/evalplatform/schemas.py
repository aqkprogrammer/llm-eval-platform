"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from evalplatform.services.datasets import CaseIn


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------- datasets
class TestCaseOut(ORM):
    __test__ = False

    id: str
    position: int
    input: str
    context: list[str]
    expected_output: str | None
    tags: list[str]
    metadata: dict[str, Any] = Field(validation_alias="metadata_")


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    cases: list[CaseIn] = Field(default_factory=list)


class DatasetSummary(ORM):
    id: str
    name: str
    description: str
    tags: list[str]
    created_at: datetime
    case_count: int = 0


class DatasetOut(DatasetSummary):
    cases: list[TestCaseOut] = Field(default_factory=list)


class CasesAppend(BaseModel):
    cases: list[CaseIn] = Field(min_length=1)


# ----------------------------------------------------------------------------- prompts
class PromptVersionCreate(BaseModel):
    system_prompt: str = ""
    user_template: str = Field(min_length=1)
    notes: str = ""


class PromptTemplateCreate(PromptVersionCreate):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class PromptVersionOut(ORM):
    id: str
    template_id: str
    version: int
    system_prompt: str
    user_template: str
    notes: str
    created_at: datetime
    variables: list[str] = Field(default_factory=list)


class PromptTemplateOut(ORM):
    id: str
    name: str
    description: str
    created_at: datetime
    versions: list[PromptVersionOut]


class PromptPreviewRequest(BaseModel):
    system_prompt: str = ""
    user_template: str
    input: str = "Example question?"
    context: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ----------------------------------------------------------------------------- models
ProviderName = Literal["mock", "anthropic", "openai", "ollama"]


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: ProviderName
    model: str = Field(min_length=1)
    temperature: float | None = Field(default=0.0, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=1, le=64000)
    params: dict[str, Any] = Field(default_factory=dict)


class ModelConfigOut(ORM):
    id: str
    name: str
    provider: str
    model: str
    temperature: float | None
    max_tokens: int
    params: dict[str, Any]
    created_at: datetime
    available: bool = True


# ----------------------------------------------------------------------------- experiments
class MetricSpec(BaseModel):
    name: str
    threshold: float | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    dataset_id: str
    prompt_version_ids: list[str] = Field(min_length=1)
    model_config_ids: list[str] = Field(min_length=1)
    metrics: list[str | MetricSpec] | None = None
    thresholds: dict[str, float | dict[str, float]] = Field(default_factory=dict)
    concurrency: int | None = Field(default=None, ge=1, le=256)
    case_limit: int | None = Field(default=None, ge=1)

    @field_validator("prompt_version_ids", "model_config_ids")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class VariantOut(ORM):
    id: str
    label: str
    prompt_version_id: str | None
    model_config_id: str | None
    prompt_snapshot: dict[str, Any]
    model_snapshot: dict[str, Any]


class ExperimentSummaryOut(ORM):
    id: str
    name: str
    description: str
    dataset_id: str
    dataset_name: str | None = None
    status: str
    source: str
    progress_total: int
    progress_done: int
    progress_failed: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    variant_count: int = 0
    gate_passed: bool | None = None


class ExperimentOut(ExperimentSummaryOut):
    metrics: list[dict[str, Any]]
    thresholds: dict[str, Any]
    concurrency: int
    summary: dict[str, Any]
    variants: list[VariantOut]


class MetricScoreOut(ORM):
    metric: str
    category: str
    value: float | None
    passed: bool | None
    explanation: str
    details: dict[str, Any]
    error: str | None


class CaseResultOut(ORM):
    id: str
    variant_id: str
    test_case_id: str
    input: str = ""
    expected_output: str | None = None
    context: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rendered_prompt: str
    output: str | None
    error: str | None
    latency_ms: float | None
    ttft_ms: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    passed: bool | None
    trace_id: str | None
    scores: list[MetricScoreOut]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


# ----------------------------------------------------------------------------- traces
class SpanIn(BaseModel):
    name: str
    kind: str = "internal"
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: float | None = None
    parent_id: str | None = None
    id: str | None = None
    status: str = "ok"
    attributes: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TraceIngest(BaseModel):
    """A production LLM call reported by an application (directly or via the ``@observe`` SDK)."""

    id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,32}$")
    name: str = "llm-call"
    input: str
    output: str
    context: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    ttft_ms: float | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    status: Literal["ok", "error"] = "ok"
    user_id: str | None = None
    session_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    start_time: datetime | None = None
    spans: list[SpanIn] = Field(default_factory=list)
    metrics: list[str] | None = None
    """Metrics to score asynchronously; defaults to ``MONITORING_METRICS``."""


class TraceIngestResponse(BaseModel):
    id: str
    score_status: str


class SpanOut(ORM):
    id: str
    trace_id: str
    parent_id: str | None
    name: str
    kind: str
    status: str
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    attributes: dict[str, Any]
    error: str | None


class TraceSummaryOut(ORM):
    id: str
    name: str
    source: str
    experiment_id: str | None
    status: str
    provider: str | None
    model: str | None
    latency_ms: float | None
    ttft_ms: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    score_status: str
    start_time: datetime
    input_preview: str = ""
    output_preview: str = ""
    tags: list[str] = Field(default_factory=list)
    flagged: bool = False


class TraceOut(TraceSummaryOut):
    input: str | None
    output: str | None
    context: list[str]
    user_id: str | None
    session_id: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    end_time: datetime | None
    spans: list[SpanOut]
    scores: list[MetricScoreOut]


# ----------------------------------------------------------------------------- comparison
class CompareRequest(BaseModel):
    baseline_experiment_id: str
    candidate_experiment_id: str
    baseline_variant_id: str | None = None
    candidate_variant_id: str | None = None
    tolerance: float = Field(default=0.02, ge=0)
