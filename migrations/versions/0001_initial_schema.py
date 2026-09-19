"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-19 06:58:40.840636
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from evalplatform.db.base import UTCDateTime

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
        sa.UniqueConstraint("name", name=op.f("uq_datasets_name")),
    )
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_datasets_created_at"), ["created_at"], unique=False)

    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "params",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_configs")),
        sa.UniqueConstraint("name", name=op.f("uq_model_configs_name")),
    )
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_model_configs_created_at"), ["created_at"], unique=False
        )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_templates")),
        sa.UniqueConstraint("name", name=op.f("uq_prompt_templates_name")),
    )
    with op.batch_alter_table("prompt_templates", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_prompt_templates_created_at"), ["created_at"], unique=False
        )

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "metrics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "thresholds",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("case_limit", sa.Integer(), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("progress_done", sa.Integer(), nullable=False),
        sa.Column("progress_failed", sa.Integer(), nullable=False),
        sa.Column(
            "summary",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_experiments_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiments")),
    )
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_experiments_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_experiments_status"), ["status"], unique=False)

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("template_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["prompt_templates.id"],
            name=op.f("fk_prompt_versions_template_id_prompt_templates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_versions")),
        sa.UniqueConstraint("template_id", "version", name="uq_prompt_version"),
    )
    with op.batch_alter_table("prompt_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_prompt_versions_created_at"), ["created_at"], unique=False
        )

    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("dataset_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column(
            "context",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_test_cases_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_cases")),
    )
    with op.batch_alter_table("test_cases", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_test_cases_created_at"), ["created_at"], unique=False)
        batch_op.create_index(
            "ix_test_cases_dataset_position", ["dataset_id", "position"], unique=False
        )

    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("experiment_id", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("prompt_version_id", sa.String(length=32), nullable=True),
        sa.Column("model_config_id", sa.String(length=32), nullable=True),
        sa.Column(
            "prompt_snapshot",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "model_snapshot",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
            name=op.f("fk_experiment_variants_experiment_id_experiments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_config_id"],
            ["model_configs.id"],
            name=op.f("fk_experiment_variants_model_config_id_model_configs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_versions.id"],
            name=op.f("fk_experiment_variants_prompt_version_id_prompt_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiment_variants")),
    )
    op.create_table(
        "traces",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("experiment_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column(
            "context",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("ttft_ms", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("user_id", sa.String(length=200), nullable=True),
        sa.Column("session_id", sa.String(length=200), nullable=True),
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("score_status", sa.String(length=20), nullable=False),
        sa.Column(
            "requested_metrics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("start_time", UTCDateTime(), nullable=False),
        sa.Column("end_time", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
            name=op.f("fk_traces_experiment_id_experiments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_traces")),
    )
    with op.batch_alter_table("traces", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_traces_created_at"), ["created_at"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_traces_experiment_id"), ["experiment_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_traces_model"), ["model"], unique=False)
        batch_op.create_index(batch_op.f("ix_traces_source"), ["source"], unique=False)
        batch_op.create_index("ix_traces_source_start", ["source", "start_time"], unique=False)
        batch_op.create_index(batch_op.f("ix_traces_start_time"), ["start_time"], unique=False)

    op.create_table(
        "case_results",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("experiment_id", sa.String(length=32), nullable=False),
        sa.Column("variant_id", sa.String(length=32), nullable=False),
        sa.Column("test_case_id", sa.String(length=32), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("ttft_ms", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
            name=op.f("fk_case_results_experiment_id_experiments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_cases.id"],
            name=op.f("fk_case_results_test_case_id_test_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["experiment_variants.id"],
            name=op.f("fk_case_results_variant_id_experiment_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_results")),
    )
    with op.batch_alter_table("case_results", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_case_results_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_case_results_experiment_id"), ["experiment_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_case_results_variant_id"), ["variant_id"], unique=False
        )

    op.create_table(
        "spans",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("parent_id", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_time", UTCDateTime(), nullable=False),
        sa.Column("end_time", UTCDateTime(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column(
            "attributes",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["trace_id"], ["traces.id"], name=op.f("fk_spans_trace_id_traces"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spans")),
    )
    with op.batch_alter_table("spans", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_spans_trace_id"), ["trace_id"], unique=False)

    op.create_table(
        "metric_scores",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("case_result_id", sa.String(length=32), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "details",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_result_id"],
            ["case_results.id"],
            name=op.f("fk_metric_scores_case_result_id_case_results"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trace_id"],
            ["traces.id"],
            name=op.f("fk_metric_scores_trace_id_traces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_scores")),
    )
    with op.batch_alter_table("metric_scores", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_metric_scores_case_result_id"), ["case_result_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_metric_scores_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_metric_scores_metric"), ["metric"], unique=False)
        batch_op.create_index(batch_op.f("ix_metric_scores_trace_id"), ["trace_id"], unique=False)


def downgrade() -> None:

    with op.batch_alter_table("metric_scores", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_metric_scores_trace_id"))
        batch_op.drop_index(batch_op.f("ix_metric_scores_metric"))
        batch_op.drop_index(batch_op.f("ix_metric_scores_created_at"))
        batch_op.drop_index(batch_op.f("ix_metric_scores_case_result_id"))

    op.drop_table("metric_scores")
    with op.batch_alter_table("spans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spans_trace_id"))

    op.drop_table("spans")
    with op.batch_alter_table("case_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_case_results_variant_id"))
        batch_op.drop_index(batch_op.f("ix_case_results_experiment_id"))
        batch_op.drop_index(batch_op.f("ix_case_results_created_at"))

    op.drop_table("case_results")
    with op.batch_alter_table("traces", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_traces_start_time"))
        batch_op.drop_index("ix_traces_source_start")
        batch_op.drop_index(batch_op.f("ix_traces_source"))
        batch_op.drop_index(batch_op.f("ix_traces_model"))
        batch_op.drop_index(batch_op.f("ix_traces_experiment_id"))
        batch_op.drop_index(batch_op.f("ix_traces_created_at"))

    op.drop_table("traces")
    op.drop_table("experiment_variants")
    with op.batch_alter_table("test_cases", schema=None) as batch_op:
        batch_op.drop_index("ix_test_cases_dataset_position")
        batch_op.drop_index(batch_op.f("ix_test_cases_created_at"))

    op.drop_table("test_cases")
    with op.batch_alter_table("prompt_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_prompt_versions_created_at"))

    op.drop_table("prompt_versions")
    with op.batch_alter_table("experiments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_experiments_status"))
        batch_op.drop_index(batch_op.f("ix_experiments_created_at"))

    op.drop_table("experiments")
    with op.batch_alter_table("prompt_templates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_prompt_templates_created_at"))

    op.drop_table("prompt_templates")
    with op.batch_alter_table("model_configs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_model_configs_created_at"))

    op.drop_table("model_configs")
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_datasets_created_at"))

    op.drop_table("datasets")
