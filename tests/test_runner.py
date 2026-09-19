from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from evalplatform.db.models import CaseResult, Dataset, Experiment, ModelConfig, Span
from evalplatform.schemas import ExperimentCreate
from evalplatform.services.context import AppServices
from evalplatform.services.datasets import CaseIn
from evalplatform.services.experiments import create_experiment
from evalplatform.services.runner import ExperimentRunner
from evalplatform.services.seed import upsert_dataset, upsert_model_config, upsert_prompt_version


async def _setup(services: AppServices, template: str, model: str, n: int = 5) -> str:
    async with services.db.sessionmaker() as session:
        cases = [CaseIn(input=f"What is {i} + {i}?", expected_output=str(2 * i)) for i in range(n)]
        ds, _ = await upsert_dataset(session, "math", cases)
        pv = await upsert_prompt_version(session, "p", "", template)
        mc = await upsert_model_config(session, {"name": model, "provider": "mock", "model": model})
        exp = await create_experiment(
            session,
            ExperimentCreate(
                name="t",
                dataset_id=ds.id,
                prompt_version_ids=[pv.id],
                model_config_ids=[mc.id],
                metrics=["exact_match", "latency_ms"],
                thresholds={"exact_match": 0.0},
            ),
            default_concurrency=4,
        )
        await session.commit()
        return exp.id


async def test_runner_records_render_errors(services: AppServices) -> None:
    exp_id = await _setup(services, "{{ input }} {{ undefined_var }}", "mock-gpt-large")
    await ExperimentRunner(services).run(exp_id)
    async with services.db.sessionmaker() as session:
        exp = await session.get(Experiment, exp_id)
        assert exp is not None
        assert exp.status == "completed"
        assert exp.progress_done == exp.progress_failed == 5
        results = (await session.scalars(select(CaseResult))).all()
        assert all(r.error and "undefined_var" in r.error and r.passed is False for r in results)
        variant = exp.summary["variants"][0]
        assert variant["errors"] == 5 and variant["pass_rate"] == 0.0


async def test_runner_retries_transient_errors(services: AppServices) -> None:
    exp_id = await _setup(services, "{{ input }}", "mock-fast-small", n=60)
    await ExperimentRunner(services).run(exp_id)
    async with services.db.sessionmaker() as session:
        exp = await session.get(Experiment, exp_id)
        assert exp is not None and exp.status == "completed"
        assert exp.progress_failed == 0
        retried = (
            await session.scalars(
                select(Span).where(Span.name == "llm.generate", Span.status == "error")
            )
        ).all()
        assert retried, "expected at least one simulated 429 that was retried"
        assert exp.summary["variants"][0]["gate_passed"] is True


async def test_runner_missing_experiment_is_marked_failed(services: AppServices) -> None:
    await ExperimentRunner(services).run("does-not-exist")  # must not raise


async def test_model_snapshot_is_immutable(services: AppServices) -> None:
    exp_id = await _setup(services, "{{ input }}", "mock-gpt-large", n=2)
    async with services.db.sessionmaker() as session:
        mc = await session.scalar(select(ModelConfig))
        assert mc is not None
        mc.model = "mock-fast-small"  # edited after the experiment was queued
        await session.commit()
    await ExperimentRunner(services).run(exp_id)
    async with services.db.sessionmaker() as session:
        exp = await session.get(Experiment, exp_id)
        assert exp is not None
        assert exp.summary["variants"][0]["model"] == "mock-gpt-large"


async def test_run_config_reuses_identical_named_dataset(
    services: AppServices, tmp_path: Path
) -> None:
    from evalplatform.config import PROJECT_ROOT
    from evalplatform.services.run_config import load_run_config, materialize
    from evalplatform.services.seed import seed_catalog

    await seed_catalog(services)
    cfg_path = PROJECT_ROOT / "examples" / "eval-config.yaml"
    cfg, base = load_run_config(cfg_path)
    async with services.db.sessionmaker() as session:
        payload = await materialize(session, cfg, base)
        ds = await session.get(Dataset, payload.dataset_id)
        assert ds is not None and ds.name == "customer-support-qa"
        # the inline prompt is identical to the seeded v2, so no new version is created
        assert len(payload.prompt_version_ids) == 1

    edited = tmp_path / "support.jsonl"
    edited.write_text(
        (PROJECT_ROOT / "data/samples/support_qa.jsonl").read_text() + '{"input": "new?"}\n'
    )
    cfg.dataset.path = str(edited)
    async with services.db.sessionmaker() as session:
        payload = await materialize(session, cfg, base)
        ds = await session.get(Dataset, payload.dataset_id)
        assert ds is not None and ds.name.startswith("customer-support-qa@")
