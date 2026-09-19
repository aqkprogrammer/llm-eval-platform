"""ORM models.

Entity overview::

    Dataset 1─* TestCase
    PromptTemplate 1─* PromptVersion
    ModelConfig
    Experiment 1─* ExperimentVariant (prompt version x model)
    Experiment 1─* CaseResult *─1 TestCase ; CaseResult 1─* MetricScore
    Trace 1─* Span ; Trace 1─* MetricScore (production monitoring)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from evalplatform.db.base import Base, JSONType, UTCDateTime, new_id, utcnow


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)

    cases: Mapped[list[TestCase]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="TestCase.position"
    )


class TestCase(TimestampMixin, Base):
    __tablename__ = "test_cases"
    __test__ = False  # keep pytest from collecting this class

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[str] = mapped_column(Text)
    context: Mapped[list[str]] = mapped_column(JSONType, default=list)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)

    dataset: Mapped[Dataset] = relationship(back_populates="cases")

    __table_args__ = (Index("ix_test_cases_dataset_position", "dataset_id", "position"),)


class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")

    versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="PromptVersion.version"
    )


class PromptVersion(TimestampMixin, Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("prompt_templates.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_template: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")

    template: Mapped[PromptTemplate] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("template_id", "version", name="uq_prompt_version"),)


class ModelConfig(TimestampMixin, Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    max_tokens: Mapped[int] = mapped_column(Integer, default=512)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    concurrency: Mapped[int] = mapped_column(Integer, default=8)
    case_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_failed: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="api")
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    dataset: Mapped[Dataset] = relationship()
    variants: Mapped[list[ExperimentVariant]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="ExperimentVariant.label",
    )


class ExperimentVariant(Base):
    """One cell of the experiment matrix: a prompt version paired with a model config."""

    __tablename__ = "experiment_variants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(300))
    prompt_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL"), nullable=True
    )
    model_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshots keep results reproducible even if the source rows change later.
    prompt_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    model_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    experiment: Mapped[Experiment] = relationship(back_populates="variants")


class CaseResult(TimestampMixin, Base):
    __tablename__ = "case_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[str] = mapped_column(
        ForeignKey("experiment_variants.id", ondelete="CASCADE"), index=True
    )
    test_case_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"))
    rendered_prompt: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    scores: Mapped[list[MetricScore]] = relationship(
        back_populates="case_result", cascade="all, delete-orphan"
    )
    test_case: Mapped[TestCase] = relationship()
    variant: Mapped[ExperimentVariant] = relationship()


class Trace(TimestampMixin, Base):
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20), default="production", index=True)
    experiment_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="ok")
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[list[str]] = mapped_column(JSONType, default=list)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    score_status: Mapped[str] = mapped_column(String(20), default="none")
    requested_metrics: Mapped[list[str]] = mapped_column(JSONType, default=list)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    end_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    spans: Mapped[list[Span]] = relationship(
        back_populates="trace", cascade="all, delete-orphan", order_by="Span.start_time"
    )
    scores: Mapped[list[MetricScore]] = relationship(
        back_populates="trace", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_traces_source_start", "source", "start_time"),)


class Span(Base):
    __tablename__ = "spans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="internal")
    status: Mapped[str] = mapped_column(String(20), default="ok")
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    end_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    trace: Mapped[Trace] = relationship(back_populates="spans")


class MetricScore(TimestampMixin, Base):
    __tablename__ = "metric_scores"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("case_results.id", ondelete="CASCADE"), nullable=True, index=True
    )
    trace_id: Mapped[str | None] = mapped_column(
        ForeignKey("traces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    metric: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50), default="quality")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    case_result: Mapped[CaseResult | None] = relationship(back_populates="scores")
    trace: Mapped[Trace | None] = relationship(back_populates="scores")
