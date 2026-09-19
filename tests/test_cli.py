from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from evalplatform.cli.main import app
from evalplatform.config import PROJECT_ROOT

runner = CliRunner()
EXAMPLE = PROJECT_ROOT / "examples" / "eval-config.yaml"


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}"


def _run(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, list(args), env={"MOCK_LATENCY_SCALE": "0", "COLUMNS": "200"})
    return result.exit_code, result.output


def test_run_passes_with_lenient_gates(tmp_path: Path, db_url: str) -> None:
    report = tmp_path / "report.json"
    code, out = _run(
        "run",
        str(EXAMPLE),
        "--database-url",
        db_url,
        "--output",
        str(report),
        "--fail-under",
        "correctness=0.3",
        "--latency-scale",
        "0",
    )
    data = json.loads(report.read_text())
    assert data["status"] == "completed"
    assert len(data["summary"]["variants"]) == 2
    assert "Evaluation results" in out
    assert code == 0, out
    assert "All quality gates passed" in out


def test_run_gate_exit_codes(tmp_path: Path, db_url: str) -> None:
    cfg = tmp_path / "suite.yaml"
    cfg.write_text(
        "name: t\n"
        f"dataset: {{path: {PROJECT_ROOT / 'data/samples/factual_qa.csv'}}}\n"
        "prompts: [{name: qa, template: '{{ input }}'}]\n"
        "models: [{provider: mock, model: mock-gpt-large}]\n"
        "metrics: [correctness, latency_ms]\n"
    )
    code, out = _run("run", str(cfg), "--ephemeral", "--fail-under", "correctness=0.1")
    assert code == 0, out
    assert "All quality gates passed" in out
    code, out = _run("run", str(cfg), "--ephemeral", "--fail-under", "correctness=0.999")
    assert code == 1
    assert "Quality gate failed" in out and "correctness" in out
    code, out = _run("run", str(cfg), "--ephemeral", "--fail-over", "latency_ms=1")
    assert code == 1


def test_run_detects_baseline_regression(tmp_path: Path) -> None:
    data_path = PROJECT_ROOT / "data/samples/support_qa.jsonl"
    good = tmp_path / "good.yaml"
    bad = tmp_path / "bad.yaml"
    common = f"dataset: {{path: {data_path}}}\nmetrics: [faithfulness, correctness]\n"
    model = "models: [{provider: mock, model: mock-fast-small, name: bot}]\n"
    good.write_text(
        "name: g\n"
        + common
        + model
        + "prompts: [{name: bot-prompt, system: 'Answer ONLY using the context.', template: '{{ context_str }} {{ input }}'}]\n"
    )
    # same prompt name so variant labels match, but no grounding instruction -> more hallucination
    bad.write_text(
        "name: b\n"
        + common
        + model
        + "prompts: [{name: bot-prompt, template: '{{ context_str }} {{ input }}'}]\n"
    )
    baseline = tmp_path / "baseline.json"
    code, _ = _run("run", str(good), "--ephemeral", "--output", str(baseline))
    assert code == 0
    # labels include the prompt version; align them to simulate "same variant, new prompt"
    report = json.loads(baseline.read_text())
    for v in report["summary"]["variants"]:
        v["label"] = "bot-prompt v1 · bot"
    baseline.write_text(json.dumps(report))
    code, out = _run(
        "run", str(bad), "--ephemeral", "--baseline", str(baseline), "--max-regression", "0.02"
    )
    assert code == 1, out
    assert "regression" in out


def test_run_usage_errors(tmp_path: Path) -> None:
    cfg = tmp_path / "broken.yaml"
    cfg.write_text("name: x\nprompts: []\n")
    code, out = _run("run", str(cfg), "--ephemeral")
    assert code == 2 and "Invalid config" in out
    code, out = _run("run", str(EXAMPLE), "--ephemeral", "--fail-under", "oops")
    assert code == 2
    missing = tmp_path / "missing.yaml"
    missing.write_text(
        "dataset: {path: nope.jsonl}\nprompts: [{name: a, template: x}]\nmodels: [{model: mock-gpt-large}]\n"
    )
    code, out = _run("run", str(missing), "--ephemeral")
    assert code == 2 and "not found" in out


def test_seed_import_compare_and_metrics(tmp_path: Path, db_url: str) -> None:
    code, out = _run("seed", "--database-url", db_url, "--traffic", "5")
    assert code == 0, out
    assert "Demo experiments completed: 3" in out
    code, out = _run("seed", "--database-url", db_url, "--traffic", "5")
    assert code == 0
    assert "Datasets created: none (already present)" in out
    assert "Demo experiments already present" in out
    assert "Production traces already present" in out

    code, out = _run(
        "import-dataset",
        str(PROJECT_ROOT / "data/samples/factual_qa.csv"),
        "--name",
        "facts",
        "--database-url",
        db_url,
    )
    assert code == 0 and "15 cases" in out

    import sqlite3

    con = sqlite3.connect(tmp_path / "cli.db")
    ids = [r[0] for r in con.execute("select id from experiments order by created_at")]
    con.close()
    code, out = _run("compare", ids[0], ids[0], "--database-url", db_url)
    assert code == 0 and "unchanged" in out
    code, out = _run("compare", ids[0], "missing", "--database-url", db_url)
    assert code == 2

    code, out = _run("metrics")
    assert code == 0 and "faithfulness" in out


def test_seed_default_traffic_volume(db_url: str) -> None:
    # Regression: the mock's simulated transient 429s must not abort traffic seeding.
    code, out = _run("seed", "--database-url", db_url)
    assert code == 0, out
    assert "Production traces" in out
