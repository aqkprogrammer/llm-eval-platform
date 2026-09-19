"""``evalctl`` - command line interface (CI gating, seeding, serving)."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from evalplatform.config import Settings, get_settings
from evalplatform.db.session import Database
from evalplatform.logging import configure_logging
from evalplatform.providers.registry import ProviderRegistry
from evalplatform.services.context import AppServices

app = typer.Typer(
    name="evalctl",
    help="LLM Eval Platform CLI: run evaluation suites, gate CI on quality, seed demo data.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console(stderr=False)
err = Console(stderr=True)

EXIT_OK, EXIT_GATE_FAILED, EXIT_USAGE, EXIT_RUN_FAILED = 0, 1, 2, 3
HEADLINE_METRICS = [
    "correctness",
    "faithfulness",
    "answer_relevancy",
    "semantic_similarity",
    "exact_match",
    "jailbreak_resistance",
    "toxicity",
    "latency_ms",
    "cost_usd",
]


def _settings(
    database_url: str | None, ephemeral: bool, latency_scale: float | None = None
) -> Settings:
    base = get_settings()
    overrides: dict[str, Any] = {"log_level": "WARNING"}
    if ephemeral:
        tmp = Path(tempfile.mkdtemp(prefix="evalctl-")) / "eval.db"
        overrides["database_url"] = f"sqlite+aiosqlite:///{tmp}"
    elif database_url:
        overrides["database_url"] = database_url
    if latency_scale is not None:
        overrides["mock_latency_scale"] = latency_scale
    return base.model_copy(update=overrides) if overrides else base


async def _services(settings: Settings, create: bool = True) -> AppServices:
    from evalplatform.tracing.otel import build_tracer_provider
    from evalplatform.tracing.tracer import Tracer, set_tracer

    db = Database(settings.database_url)
    if create:
        await db.create_all()
    set_tracer(Tracer(build_tracer_provider(settings)))
    return AppServices(settings=settings, db=db, providers=ProviderRegistry(settings))


def _parse_bounds(values: list[str], key: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for item in values:
        if "=" not in item:
            raise typer.BadParameter(f"expected METRIC=VALUE, got '{item}'")
        metric, raw = item.split("=", 1)
        try:
            out[metric.strip()] = {key: float(raw)}
        except ValueError as exc:
            raise typer.BadParameter(f"'{raw}' is not a number") from exc
    return out


def _fmt(metric: str, value: float | None) -> str:
    if value is None:
        return "-"
    if metric.endswith("_ms"):
        return f"{value:,.0f}ms"
    if metric == "cost_usd":
        return f"${value:.5f}"
    return f"{value:.3f}"


def _render_summary(summary: dict[str, Any]) -> None:
    variants = summary.get("variants", [])
    present = [m for m in HEADLINE_METRICS if any(m in v["metrics"] for v in variants)]
    table = Table(title="Evaluation results", show_lines=False, header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("Variant")
    table.add_column("Score", justify="right")
    table.add_column("Pass", justify="right")
    for m in present:
        table.add_column(m, justify="right")
    table.add_column("Gate", justify="center")
    for v in variants:
        gate = v.get("gate_passed")
        table.add_row(
            str(v.get("rank", "")),
            v["label"],
            _fmt("score", v.get("composite_score")),
            "-" if v.get("pass_rate") is None else f"{v['pass_rate']:.0%}",
            *[_fmt(m, (v["metrics"].get(m) or {}).get("mean")) for m in present],
            "[green]PASS[/]" if gate else "[red]FAIL[/]" if gate is False else "-",
        )
    console.print(table)
    for v in variants:
        for g in v.get("gates", []):
            if not g["passed"]:
                bound = f">= {g['min']}" if "min" in g else f"<= {g['max']}"
                actual = "n/a" if g["actual"] is None else f"{g['actual']:.4g}"
                console.print(
                    f"  [red]x[/] {v['label']}: {g['metric']} = {actual} (required {bound})"
                )


def _baseline_regressions(
    summary: dict[str, Any], baseline: dict[str, Any], tolerance: float
) -> list[str]:
    from evalplatform.services.comparison import is_regression

    base_by_label = {v["label"]: v for v in baseline.get("summary", baseline).get("variants", [])}
    problems: list[str] = []
    for v in summary.get("variants", []):
        b = base_by_label.get(v["label"])
        if b is None:
            continue
        for metric, agg in v["metrics"].items():
            bm = (b["metrics"].get(metric) or {}).get("mean")
            cm = agg.get("mean")
            if bm is None or cm is None:
                continue
            delta, status = is_regression(metric, bm, cm, tolerance)
            if status == "regressed":
                problems.append(f"{v['label']}: {metric} {bm:.4g} -> {cm:.4g} ({delta:+.4g})")
    return problems


@app.command()
def run(
    config: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Run config YAML")],
    fail_under: Annotated[
        list[str] | None,
        typer.Option(
            "--fail-under",
            help="METRIC=VALUE: fail if the mean is below VALUE "
            "(use pass_rate=0.9 for the share of passing cases). Repeatable.",
        ),
    ] = None,
    fail_over: Annotated[
        list[str] | None,
        typer.Option(
            "--fail-over",
            help="METRIC=VALUE: fail if the mean is above VALUE "
            "(latency_ms, cost_usd, toxicity...). Repeatable.",
        ),
    ] = None,
    baseline: Annotated[
        Path | None, typer.Option(help="Previous JSON report; fail on metric regressions vs it.")
    ] = None,
    max_regression: Annotated[
        float, typer.Option(help="Tolerance for --baseline comparisons.")
    ] = 0.02,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write a JSON report.")
    ] = None,
    database_url: Annotated[
        str | None, typer.Option(help="Persist results to this database.")
    ] = None,
    ephemeral: Annotated[bool, typer.Option(help="Use a throwaway SQLite database.")] = False,
    concurrency: Annotated[int | None, typer.Option(help="Override max concurrent calls.")] = None,
    latency_scale: Annotated[
        float | None, typer.Option(help="Mock provider latency multiplier (0 = no sleeping).")
    ] = None,
) -> None:
    """Run an evaluation suite and exit non-zero if quality gates fail (for CI)."""
    from evalplatform.services.experiments import ExperimentValidationError, create_experiment
    from evalplatform.services.run_config import RunConfigError, load_run_config, materialize
    from evalplatform.services.runner import ExperimentRunner
    from evalplatform.services.stats import evaluate_gates, normalize_thresholds

    configure_logging("WARNING")
    try:
        cfg, base_dir = load_run_config(config)
        extra = {**_parse_bounds(fail_under or [], "min"), **_parse_bounds(fail_over or [], "max")}
    except (RunConfigError, typer.BadParameter) as exc:
        err.print(f"[red]error:[/] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    if concurrency:
        cfg.concurrency = concurrency
    baseline_report = None
    if baseline is not None:
        try:
            baseline_report = json.loads(baseline.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            err.print(f"[red]error:[/] cannot read baseline report: {exc}")
            raise typer.Exit(EXIT_USAGE) from exc

    settings = _settings(database_url, ephemeral, latency_scale)

    async def _go() -> dict[str, Any]:
        services = await _services(settings)
        try:
            async with services.db.sessionmaker() as session:
                payload = await materialize(session, cfg, base_dir)
                payload.thresholds = {**payload.thresholds, **extra}
                exp = await create_experiment(
                    session, payload, default_concurrency=settings.default_concurrency, source="cli"
                )
                await session.commit()
                exp_id, total = exp.id, exp.progress_total
            console.print(
                f"Running [bold]{cfg.name}[/]: {len(payload.prompt_version_ids)} prompt(s) x "
                f"{len(payload.model_config_ids)} model(s), {total} generations"
            )
            with console.status("Evaluating..."):
                await ExperimentRunner(services).run(exp_id)
            from evalplatform.db.models import Experiment

            async with services.db.sessionmaker() as session:
                e = await session.get(Experiment, exp_id)
                assert e is not None
                return {
                    "experiment_id": e.id,
                    "status": e.status,
                    "error": e.error,
                    "thresholds": e.thresholds,
                    "summary": e.summary,
                    "database": settings.database_url.split("@")[-1],
                }
        finally:
            await services.aclose()

    try:
        report = asyncio.run(_go())
    except (RunConfigError, ExperimentValidationError) as exc:
        err.print(f"[red]error:[/] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    if report["status"] != "completed":
        err.print(f"[red]Run {report['status']}:[/] {report['error']}")
        raise typer.Exit(EXIT_RUN_FAILED)

    summary = report["summary"]
    # Re-evaluate gates so CLI-only thresholds are always applied.
    thresholds = normalize_thresholds(report["thresholds"])
    for v in summary["variants"]:
        v["gates"] = evaluate_gates(v, thresholds)
        v["gate_passed"] = all(g["passed"] for g in v["gates"]) if v["gates"] else None
    _render_summary(summary)
    gate_failed = any(v["gate_passed"] is False for v in summary["variants"])
    regressions = (
        _baseline_regressions(summary, baseline_report, max_regression) if baseline_report else []
    )
    for r in regressions:
        console.print(f"  [red]regression[/] {r}")
    report["regressions"] = regressions
    report["passed"] = not gate_failed and not regressions
    if output:
        output.write_text(json.dumps(report, indent=2, default=str))
        console.print(f"Report written to {output}")
    console.print(f"Experiment id: {report['experiment_id']} ({report['database']})")
    if report["passed"]:
        console.print("[bold green]All quality gates passed.[/]")
        raise typer.Exit(EXIT_OK)
    console.print("[bold red]Quality gate failed.[/]")
    raise typer.Exit(EXIT_GATE_FAILED)


@app.command()
def compare(
    baseline: Annotated[str, typer.Argument(help="Baseline experiment id")],
    candidate: Annotated[str, typer.Argument(help="Candidate experiment id")],
    tolerance: Annotated[float, typer.Option()] = 0.02,
    database_url: Annotated[str | None, typer.Option()] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print raw JSON.")] = False,
) -> None:
    """Compare two stored experiments; exits 1 if the candidate regressed."""
    from evalplatform.services.comparison import ComparisonError, compare_experiments

    configure_logging("WARNING")
    settings = _settings(database_url, False)

    async def _go() -> dict[str, Any]:
        services = await _services(settings, create=False)
        try:
            async with services.db.sessionmaker() as session:
                return await compare_experiments(session, baseline, candidate, tolerance=tolerance)
        finally:
            await services.aclose()

    try:
        result = asyncio.run(_go())
    except ComparisonError as exc:
        err.print(f"[red]error:[/] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    if json_out:
        console.print_json(json.dumps(result, default=str))
    else:
        table = Table(title=f"{result['baseline']['label']}  vs  {result['candidate']['label']}")
        for col in ("Metric", "Baseline", "Candidate", "Delta", "Status"):
            table.add_column(col, justify="left" if col == "Metric" else "right")
        colors = {"regressed": "red", "improved": "green", "unchanged": "dim", "missing": "yellow"}
        for m in result["metrics"]:
            table.add_row(
                m["metric"],
                _fmt(m["metric"], m["baseline"]),
                _fmt(m["metric"], m["candidate"]),
                "-" if m["delta"] is None else f"{m['delta']:+.4g}",
                f"[{colors[m['status']]}]{m['status']}[/]",
            )
        console.print(table)
        cs = result["case_summary"]
        console.print(
            f"Cases: {cs['improved']} improved, {cs['regressed']} regressed, "
            f"{cs['mixed']} mixed, {cs['unchanged']} unchanged"
        )
    raise typer.Exit(EXIT_GATE_FAILED if result["has_regression"] else EXIT_OK)


@app.command()
def seed(
    demo: Annotated[bool, typer.Option(help="Also run demo experiments.")] = True,
    traffic: Annotated[int, typer.Option(help="Simulated production traces to ingest.")] = 160,
    force: Annotated[bool, typer.Option(help="Re-run demos even if demo data exists.")] = False,
    database_url: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Load sample datasets, prompts and models (idempotent), plus optional demo data."""
    from evalplatform.services.seed import (
        seed_catalog,
        seed_demo_experiments,
        seed_production_traffic,
    )

    configure_logging("WARNING")
    settings = _settings(database_url, False)

    async def _go() -> None:
        services = await _services(settings)
        try:
            created = await seed_catalog(services)
            console.print(
                f"Datasets created: {', '.join(created['datasets']) or 'none (already present)'}"
            )
            console.print(f"Prompt versions: {', '.join(created['prompt_versions'])}")
            console.print(f"Model configs: {', '.join(created['models'])}")
            if demo:
                with console.status("Running demo experiments..."):
                    ids = await seed_demo_experiments(services, force=force)
                console.print(
                    f"Demo experiments completed: {len(ids)}"
                    if ids
                    else "Demo experiments already present (use --force to re-run)"
                )
            if traffic:
                with console.status("Simulating production traffic..."):
                    n = await seed_production_traffic(services, traffic, force=force)
                console.print(
                    f"Production traces ingested and scored: {n}"
                    if n
                    else "Production traces already present (use --force to add more)"
                )
        finally:
            await services.aclose()

    asyncio.run(_go())


@app.command("import-dataset")
def import_dataset(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    name: Annotated[str | None, typer.Option()] = None,
    database_url: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Import a JSONL/JSON/CSV dataset file."""
    from evalplatform.services.datasets import DatasetImportError, detect_format, parse_cases
    from evalplatform.services.seed import upsert_dataset

    settings = _settings(database_url, False)
    try:
        cases = parse_cases(path.read_bytes(), detect_format(path.name))
    except DatasetImportError as exc:
        err.print(f"[red]error:[/] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    async def _go() -> tuple[str, bool]:
        services = await _services(settings)
        try:
            async with services.db.sessionmaker() as session:
                ds, created = await upsert_dataset(session, name or path.stem, cases)
                await session.commit()
                return ds.id, created
        finally:
            await services.aclose()

    ds_id, created = asyncio.run(_go())
    if not created:
        err.print(f"[yellow]Dataset '{name or path.stem}' already exists ({ds_id}).[/]")
        raise typer.Exit(EXIT_USAGE)
    console.print(f"Imported {len(cases)} cases into dataset {ds_id}")


@app.command()
def metrics() -> None:
    """List available metrics."""
    from evalplatform.metrics.registry import all_metric_classes

    table = Table(title="Metrics")
    for col in ("Name", "Category", "Direction", "Threshold", "Backend", "Available"):
        table.add_column(col)
    for cls in all_metric_classes():
        table.add_row(
            cls.name,
            cls.category,
            "higher" if cls.higher_is_better else "lower",
            "-" if cls.default_threshold is None else str(cls.default_threshold),
            cls.backend,
            "yes" if cls.is_available() else "no (install extra)",
        )
    console.print(table)


@app.command()
def migrate(revision: Annotated[str, typer.Argument()] = "head") -> None:
    """Apply Alembic migrations to DATABASE_URL."""
    from alembic import command
    from alembic.config import Config

    from evalplatform.config import PROJECT_ROOT

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    command.upgrade(cfg, revision)
    console.print(f"Database migrated to {revision}")


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option()] = False,
) -> None:
    """Start the API (and the built dashboard, if present)."""
    import uvicorn

    uvicorn.run("evalplatform.api.main:app", host=host, port=port, reload=reload, log_config=None)


def main() -> None:  # pragma: no cover
    sys.exit(app())


if __name__ == "__main__":  # pragma: no cover
    main()
