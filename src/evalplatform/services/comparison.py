"""Side-by-side comparison of two experiments (or two variants) and regression detection."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from evalplatform.db.models import CaseResult, Experiment, TestCase
from evalplatform.services.stats import ScorePoint, aggregate, composite_score, metric_meta


class ComparisonError(ValueError):
    pass


async def _load_side(
    session: AsyncSession, experiment_id: str, variant_id: str | None
) -> tuple[Experiment, list[CaseResult], str]:
    exp = await session.get(Experiment, experiment_id, options=[selectinload(Experiment.variants)])
    if exp is None:
        raise ComparisonError(f"Experiment '{experiment_id}' not found")
    label = exp.name
    stmt = (
        select(CaseResult)
        .where(CaseResult.experiment_id == experiment_id)
        .options(selectinload(CaseResult.scores))
    )
    if variant_id:
        variant = next((v for v in exp.variants if v.id == variant_id), None)
        if variant is None:
            raise ComparisonError(
                f"Variant '{variant_id}' does not belong to experiment '{exp.name}'"
            )
        stmt = stmt.where(CaseResult.variant_id == variant_id)
        label = f"{exp.name} / {variant.label}"
    elif len(exp.variants) > 1:
        label = f"{exp.name} (all {len(exp.variants)} variants)"
    return exp, list((await session.scalars(stmt)).all()), label


def is_regression(
    metric: str, baseline: float, candidate: float, tolerance: float
) -> tuple[float, str]:
    """Return ``(delta, status)``.

    Score metrics use an absolute tolerance; unit metrics (ms, usd, tokens) a relative one.
    """
    meta = metric_meta(metric)
    delta = candidate - baseline
    signed = delta if meta["higher_is_better"] else -delta
    margin = tolerance if meta["unit"] == "score" else abs(baseline) * max(tolerance, 0.1)
    if signed < -margin:
        return delta, "regressed"
    if signed > margin:
        return delta, "improved"
    return delta, "unchanged"


def _per_case_means(results: list[CaseResult]) -> dict[str, dict[str, Any]]:
    by_case: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    outputs: dict[str, str | None] = {}
    passed: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        outputs.setdefault(r.test_case_id, r.output)
        if r.passed is not None:
            passed[r.test_case_id].append(r.passed)
        for s in r.scores:
            if s.value is not None:
                by_case[r.test_case_id][s.metric].append(s.value)
    out: dict[str, dict[str, Any]] = {}
    for case_id in set(outputs) | set(by_case):
        out[case_id] = {
            "output": outputs.get(case_id),
            "passed": all(passed[case_id]) if passed.get(case_id) else None,
            "metrics": {m: sum(v) / len(v) for m, v in by_case[case_id].items() if v},
        }
    return out


def _case_status(regressed: list[str], improved: list[str]) -> str:
    if regressed and improved:
        return "mixed"
    if regressed:
        return "regressed"
    if improved:
        return "improved"
    return "unchanged"


async def compare_experiments(
    session: AsyncSession,
    baseline_id: str,
    candidate_id: str,
    baseline_variant_id: str | None = None,
    candidate_variant_id: str | None = None,
    tolerance: float = 0.02,
) -> dict[str, Any]:
    base_exp, base_results, base_label = await _load_side(session, baseline_id, baseline_variant_id)
    cand_exp, cand_results, cand_label = await _load_side(
        session, candidate_id, candidate_variant_id
    )

    base_aggs = aggregate(
        ScorePoint(s.metric, s.value, s.passed) for r in base_results for s in r.scores
    )
    cand_aggs = aggregate(
        ScorePoint(s.metric, s.value, s.passed) for r in cand_results for s in r.scores
    )

    metrics: list[dict[str, Any]] = []
    for name in sorted(set(base_aggs) | set(cand_aggs)):
        b, c = base_aggs.get(name), cand_aggs.get(name)
        if (b is None or b["mean"] is None) and (c is None or c["mean"] is None):
            continue  # metric skipped on both sides (e.g. jailbreak_resistance on benign data)
        meta = metric_meta(name)
        row: dict[str, Any] = {
            "metric": name,
            **meta,
            "baseline": b["mean"] if b else None,
            "candidate": c["mean"] if c else None,
            "baseline_pass_rate": b["pass_rate"] if b else None,
            "candidate_pass_rate": c["pass_rate"] if c else None,
            "delta": None,
            "status": "missing",
        }
        if b and c and b["mean"] is not None and c["mean"] is not None:
            delta, status = is_regression(name, b["mean"], c["mean"], tolerance)
            row.update(delta=round(delta, 6), status=status)
        metrics.append(row)

    same_dataset = base_exp.dataset_id == cand_exp.dataset_id
    cases: list[dict[str, Any]] = []
    if same_dataset:
        base_cases = _per_case_means(base_results)
        cand_cases = _per_case_means(cand_results)
        tc_rows = (
            await session.scalars(
                select(TestCase).where(TestCase.id.in_(set(base_cases) | set(cand_cases)))
            )
        ).all()
        tcs = {t.id: t for t in tc_rows}
        for case_id in sorted(
            set(base_cases) & set(cand_cases),
            key=lambda cid: tcs[cid].position if cid in tcs else 0,
        ):
            bc, cc = base_cases[case_id], cand_cases[case_id]
            deltas: dict[str, float] = {}
            regressed: list[str] = []
            improved: list[str] = []
            for m in sorted(set(bc["metrics"]) & set(cc["metrics"])):
                d, status = is_regression(m, bc["metrics"][m], cc["metrics"][m], tolerance)
                deltas[m] = round(d, 6)
                if status == "regressed":
                    regressed.append(m)
                elif status == "improved":
                    improved.append(m)
            tc = tcs.get(case_id)
            # Case status reflects quality (0-1 score) metrics; latency/cost deltas are still
            # reported per metric but would otherwise mark almost every case as "mixed".
            q_reg = [m for m in regressed if metric_meta(m)["unit"] == "score"]
            q_imp = [m for m in improved if metric_meta(m)["unit"] == "score"]
            cases.append(
                {
                    "test_case_id": case_id,
                    "input": tc.input if tc else "",
                    "expected_output": tc.expected_output if tc else None,
                    "baseline_output": bc["output"],
                    "candidate_output": cc["output"],
                    "baseline_passed": bc["passed"],
                    "candidate_passed": cc["passed"],
                    "baseline_metrics": {k: round(v, 6) for k, v in bc["metrics"].items()},
                    "candidate_metrics": {k: round(v, 6) for k, v in cc["metrics"].items()},
                    "deltas": deltas,
                    "regressed_metrics": regressed,
                    "improved_metrics": improved,
                    "status": _case_status(q_reg, q_imp),
                }
            )

    regressions = [m["metric"] for m in metrics if m["status"] == "regressed"]
    return {
        "baseline": {
            "experiment_id": base_exp.id,
            "variant_id": baseline_variant_id,
            "label": base_label,
            "composite_score": composite_score(base_aggs),
            "cases": len(base_results),
        },
        "candidate": {
            "experiment_id": cand_exp.id,
            "variant_id": candidate_variant_id,
            "label": cand_label,
            "composite_score": composite_score(cand_aggs),
            "cases": len(cand_results),
        },
        "same_dataset": same_dataset,
        "tolerance": tolerance,
        "metrics": metrics,
        "regressions": regressions,
        "has_regression": bool(regressions),
        "case_summary": {
            s: sum(1 for c in cases if c["status"] == s)
            for s in ("improved", "regressed", "mixed", "unchanged")
        },
        "cases": cases,
    }
