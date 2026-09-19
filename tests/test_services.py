from __future__ import annotations

import pytest

from evalplatform.services.comparison import is_regression
from evalplatform.services.datasets import DatasetImportError, parse_cases
from evalplatform.services.prompts import (
    PromptRenderError,
    build_variables,
    render,
    validate_template,
)
from evalplatform.services.stats import (
    ScorePoint,
    aggregate,
    composite_score,
    evaluate_gates,
    normalize_thresholds,
    percentile,
)
from evalplatform.tracing.tracer import Tracer


# ----------------------------------------------------------------------------- datasets
def test_parse_jsonl_with_aliases() -> None:
    text = (
        '{"question": "Q1", "answer": "A1", "contexts": ["c1", "c2"], "tags": "a,b", "difficulty": "hard"}\n'
        "\n"
        '{"input": "Q2"}\n'
    )
    cases = parse_cases(text, "jsonl")
    assert cases[0].input == "Q1" and cases[0].expected_output == "A1"
    assert cases[0].context == ["c1", "c2"] and cases[0].tags == ["a", "b"]
    assert cases[0].metadata == {"difficulty": "hard"}
    assert cases[1].expected_output is None and cases[1].context == []


def test_parse_csv() -> None:
    text = 'input,expected_output,context,tags,metadata\nQ,A,"[""x"",""y""]",t1;t2,"{""k"": 1}"\n'
    [case] = parse_cases(text.encode(), "csv")
    assert case.context == ["x", "y"] and case.tags == ["t1", "t2"] and case.metadata == {"k": 1}


def test_parse_json_object() -> None:
    assert len(parse_cases('{"cases": [{"input": "a"}, {"input": "b"}]}', "json")) == 2


@pytest.mark.parametrize(
    ("content", "fmt", "match"),
    [
        ('{"input": "x"}\n{bad', "jsonl", "Invalid JSON"),
        ('{"expected_output": "x"}', "jsonl", "Row 1"),
        ("", "jsonl", "No test cases"),
        ("a", "xml", "Unsupported"),
    ],
)
def test_parse_errors(content: str, fmt: str, match: str) -> None:
    with pytest.raises(DatasetImportError, match=match):
        parse_cases(content, fmt)


# ----------------------------------------------------------------------------- prompts
def test_render_prompt() -> None:
    v = build_variables("What?", ["c1", "c2"], metadata={"customer": "Ann"})
    out = render("Hi {{ customer }}.\n{{ context_str }}\nQ: {{ input }}", v)
    assert out == "Hi Ann.\n- c1\n- c2\nQ: What?"
    assert validate_template("{{ input }} {{ foo }}") == ["foo", "input"]


def test_render_errors() -> None:
    with pytest.raises(PromptRenderError, match="render"):
        render("{{ missing }}", build_variables("x"))
    with pytest.raises(PromptRenderError, match="Invalid template"):
        validate_template("{% if %}")
    with pytest.raises(PromptRenderError):  # sandbox blocks attribute escapes
        render("{{ input.__class__.__mro__[1].__subclasses__() }}", build_variables("x"))


# ----------------------------------------------------------------------------- stats
def test_aggregate_and_composite() -> None:
    aggs = aggregate(
        [
            ScorePoint("faithfulness", 1.0, True),
            ScorePoint("faithfulness", 0.5, False),
            ScorePoint("faithfulness", None, None),
            ScorePoint("toxicity", 0.2, True),
            ScorePoint("latency_ms", 100, True),
            ScorePoint("latency_ms", 300, True),
        ]
    )
    assert aggs["faithfulness"]["mean"] == 0.75
    assert aggs["faithfulness"]["pass_rate"] == 0.5
    assert aggs["faithfulness"]["skipped"] == 1
    assert aggs["latency_ms"]["p50"] == 200
    # composite: mean(0.75, 1 - 0.2); latency excluded (not a quality score)
    assert composite_score(aggs) == pytest.approx(0.775)


def test_percentile() -> None:
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([5], 0.95) == 5


def test_thresholds_and_gates() -> None:
    t = normalize_thresholds(
        {"faithfulness": 0.8, "latency_ms": 1500, "correctness": {"min": 0.5, "max": 1}}
    )
    assert t["faithfulness"] == {"min": 0.8}
    assert t["latency_ms"] == {"max": 1500.0}
    summary = {
        "pass_rate": 0.9,
        "metrics": {"faithfulness": {"mean": 0.7}, "latency_ms": {"mean": 900}},
    }
    gates = {
        g["metric"]: g["passed"]
        for g in evaluate_gates(summary, {**t, **normalize_thresholds({"pass_rate": 0.8})})
    }
    assert gates == {
        "faithfulness": False,
        "latency_ms": True,
        "correctness": False,
        "pass_rate": True,
    }
    with pytest.raises(ValueError, match="min"):
        normalize_thresholds({"x": {"foo": 1}})


def test_is_regression() -> None:
    assert is_regression("faithfulness", 0.9, 0.8, 0.02)[1] == "regressed"
    assert is_regression("faithfulness", 0.9, 0.91, 0.02)[1] == "unchanged"
    assert is_regression("toxicity", 0.1, 0.0, 0.02)[1] == "improved"
    assert is_regression("latency_ms", 1000, 1050, 0.02)[1] == "unchanged"  # within 10% floor
    assert is_regression("latency_ms", 1000, 1300, 0.02)[1] == "regressed"


# ----------------------------------------------------------------------------- tracer
async def test_tracer_nesting_and_errors() -> None:
    tracer = Tracer(None)
    with tracer.trace("t") as collector:
        async with tracer.span("root", kind="chain") as root:
            async with tracer.span("child", kind="llm", model="m") as child:
                child.set("tokens", 5)
            with pytest.raises(ValueError):
                async with tracer.span("bad"):
                    raise ValueError("boom")
    spans = {s.name: s for s in collector.spans}
    assert spans["child"].parent_id == root.id
    assert spans["child"].attributes == {"model": "m", "tokens": 5}
    assert spans["bad"].status == "error" and "boom" in (spans["bad"].error or "")
    assert all(s.trace_id == collector.trace_id for s in collector.spans)
    assert spans["root"].duration_ms is not None


async def test_tracer_exports_to_otel() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = Tracer(provider)
    with tracer.trace("t"):
        async with tracer.span("outer"), tracer.span("inner", kind="llm", model="m"):
            pass
    finished = {s.name: s for s in exporter.get_finished_spans()}
    assert set(finished) == {"outer", "inner"}
    assert finished["inner"].parent is not None
    assert finished["inner"].attributes["model"] == "m"
