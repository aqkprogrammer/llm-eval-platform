from __future__ import annotations

import io

import httpx
from fastapi import FastAPI

from tests.helpers import catalog, experiment_payload


async def run_experiment(client: httpx.AsyncClient, app: FastAPI, payload: dict) -> dict:
    resp = await client.post("/api/experiments", json=payload)
    assert resp.status_code == 202, resp.text
    exp = resp.json()
    await app.state.jobs.wait(exp["id"])
    return (await client.get(f"/api/experiments/{exp['id']}")).json()


async def test_health(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/health")).json()
    assert body["status"] == "ok"
    assert body["database"]["dialect"] == "sqlite"
    assert body["providers"]["mock"] is True


async def test_metrics_and_providers(client: httpx.AsyncClient) -> None:
    metrics = {m["name"]: m for m in (await client.get("/api/metrics")).json()}
    assert metrics["faithfulness"]["requires"] == ["context"]
    assert metrics["latency_ms"]["higher_is_better"] is False
    prov = (await client.get("/api/providers")).json()
    assert "claude-sonnet-5" in prov["pricing"]


async def test_experiment_lifecycle(
    client: httpx.AsyncClient, app: FastAPI, seeded: object
) -> None:
    cat = await catalog(client)
    exp = await run_experiment(client, app, experiment_payload(cat))
    assert exp["status"] == "completed", exp["error"]
    assert exp["progress_done"] == exp["progress_total"] == 6 * 4
    assert len(exp["variants"]) == 4
    variants = exp["summary"]["variants"]
    assert [v["rank"] for v in variants] == [1, 2, 3, 4]
    assert all("faithfulness" in v["metrics"] for v in variants)
    assert all(v["gates"][0]["metric"] == "faithfulness" for v in variants)
    # the careful model with the grounded prompt should beat the sloppy one with the naive prompt
    by_label = {v["label"]: v for v in variants}
    assert (
        by_label["support-assistant v2 · mock-gpt-large"]["composite_score"]
        > by_label["support-assistant v1 · mock-fast-small"]["composite_score"]
    )

    results = (
        await client.get(f"/api/experiments/{exp['id']}/results", params={"limit": 5})
    ).json()
    assert results["total"] == 24 and len(results["items"]) == 5
    item = results["items"][0]
    assert item["output"] and item["trace_id"] and item["input"]
    assert {s["metric"] for s in item["scores"]} == {
        "correctness",
        "faithfulness",
        "answer_relevancy",
        "toxicity",
        "latency_ms",
        "cost_usd",
    }
    variant_id = exp["variants"][0]["id"]
    filtered = (
        await client.get(f"/api/experiments/{exp['id']}/results", params={"variant_id": variant_id})
    ).json()
    assert filtered["total"] == 6
    failing = (
        await client.get(f"/api/experiments/{exp['id']}/results", params={"passed": False})
    ).json()
    assert all(i["passed"] is False for i in failing["items"])

    trace = (await client.get(f"/api/traces/{item['trace_id']}")).json()
    kinds = {s["kind"] for s in trace["spans"]}
    assert {"chain", "llm", "metric"} <= kinds
    assert {s["metric"] for s in trace["scores"]} == {s["metric"] for s in item["scores"]}
    names = {s["name"] for s in trace["spans"]}
    assert "judge.correctness" in names and "metric.faithfulness" in names

    listing = (await client.get("/api/experiments")).json()
    assert listing[0]["id"] == exp["id"] and listing[0]["variant_count"] == 4

    lb = (await client.get("/api/leaderboard")).json()["rows"]
    assert len(lb) == 4 and lb[0]["composite_score"] >= lb[-1]["composite_score"]


async def test_compare_experiments(client: httpx.AsyncClient, app: FastAPI, seeded: object) -> None:
    cat = await catalog(client)
    v1, v2 = (v["id"] for v in cat["prompts"]["support-assistant"]["versions"])
    small = cat["models"]["mock-fast-small"]["id"]
    base = await run_experiment(
        client,
        app,
        experiment_payload(cat, prompt_version_ids=[v1], model_config_ids=[small], case_limit=None),
    )
    cand = await run_experiment(
        client,
        app,
        experiment_payload(cat, prompt_version_ids=[v2], model_config_ids=[small], case_limit=None),
    )
    cmp = (
        await client.get("/api/compare", params={"baseline": base["id"], "candidate": cand["id"]})
    ).json()
    assert cmp["same_dataset"] is True
    assert len(cmp["cases"]) == 15
    metrics = {m["metric"]: m for m in cmp["metrics"]}
    assert metrics["faithfulness"]["status"] == "improved"  # grounded prompt reduces hallucination
    reverse = (
        await client.get("/api/compare", params={"baseline": cand["id"], "candidate": base["id"]})
    ).json()
    assert reverse["has_regression"] is True and "faithfulness" in reverse["regressions"]
    assert sum(reverse["case_summary"].values()) == 15

    # variant-level comparison inside one experiment
    multi = await run_experiment(client, app, experiment_payload(cat))
    va, vb = multi["variants"][0]["id"], multi["variants"][1]["id"]
    within = (
        await client.get(
            "/api/compare",
            params={
                "baseline": multi["id"],
                "candidate": multi["id"],
                "baseline_variant": va,
                "candidate_variant": vb,
            },
        )
    ).json()
    assert within["baseline"]["cases"] == 6
    assert (
        await client.get("/api/compare", params={"baseline": "nope", "candidate": multi["id"]})
    ).status_code == 404


async def test_experiment_validation(client: httpx.AsyncClient, seeded: object) -> None:
    cat = await catalog(client)
    r = await client.post("/api/experiments", json=experiment_payload(cat, metrics=["nope"]))
    assert r.status_code == 422 and "nope" in r.json()["detail"]
    r = await client.post("/api/experiments", json=experiment_payload(cat, dataset_id="missing"))
    assert r.status_code == 422
    r = await client.post(
        "/api/experiments", json=experiment_payload(cat, metrics=["ragas_faithfulness"])
    )
    assert r.status_code == 422
    r = await client.post("/api/experiments", json=experiment_payload(cat, model_config_ids=[]))
    assert r.status_code == 422
    assert (await client.get("/api/experiments/missing")).status_code == 404


async def test_cancel_experiment(client: httpx.AsyncClient, app: FastAPI, seeded: object) -> None:
    app.state.services.providers.get("mock").latency_scale = 1.0
    cat = await catalog(client)
    exp = (
        await client.post(
            "/api/experiments", json=experiment_payload(cat, case_limit=None, concurrency=1)
        )
    ).json()
    r = await client.post(f"/api/experiments/{exp['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert (await client.post(f"/api/experiments/{exp['id']}/cancel")).status_code == 409
    assert (await client.delete(f"/api/experiments/{exp['id']}")).status_code == 204


async def test_datasets_api(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/datasets",
        json={
            "name": "tiny",
            "cases": [{"input": "Q", "expected_output": "A", "context": ["ctx"]}],
        },
    )
    assert r.status_code == 201 and r.json()["case_count"] == 1
    ds_id = r.json()["id"]
    assert (await client.post("/api/datasets", json={"name": "tiny"})).status_code == 409
    r = await client.post(f"/api/datasets/{ds_id}/cases", json={"cases": [{"input": "Q2"}]})
    assert [c["position"] for c in r.json()["cases"]] == [0, 1]
    export = await client.get(f"/api/datasets/{ds_id}/export")
    assert export.text.count("\n") == 2

    csv_bytes = b"input,expected_output,tags\nWhat is 2+2?,4,math\n"
    r = await client.post(
        "/api/datasets/import",
        files={"file": ("math.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"description": "d"},
    )
    assert r.status_code == 201 and r.json()["name"] == "math"
    r = await client.post(
        "/api/datasets/import",
        files={"file": ("bad.jsonl", io.BytesIO(b"{oops"), "application/json")},
    )
    assert r.status_code == 422
    assert (await client.delete(f"/api/datasets/{ds_id}")).status_code == 204
    assert (await client.get(f"/api/datasets/{ds_id}")).status_code == 404


async def test_prompts_api(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/prompts", json={"name": "p", "user_template": "Q: {{ input }}"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["versions"][0]["variables"] == ["input"]
    r = await client.post(
        f"/api/prompts/{pid}/versions", json={"user_template": "{{ input }} {{ context_str }}"}
    )
    assert r.status_code == 201 and r.json()["version"] == 2
    assert (
        await client.post(f"/api/prompts/{pid}/versions", json={"user_template": "{% if %}"})
    ).status_code == 422
    assert len((await client.get(f"/api/prompts/{pid}")).json()["versions"]) == 2
    prev = await client.post(
        "/api/prompts/preview",
        json={"user_template": "{{ input }}|{{ context_str }}", "input": "hi", "context": ["a"]},
    )
    assert prev.json()["user"] == "hi|- a"
    assert (
        await client.post("/api/prompts", json={"name": "p", "user_template": "x"})
    ).status_code == 409


async def test_models_api(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/models",
        json={
            "name": "claude",
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "temperature": None,
        },
    )
    assert r.status_code == 201 and r.json()["available"] is False
    assert (
        await client.post("/api/models", json={"name": "x", "provider": "bogus", "model": "m"})
    ).status_code == 422
    assert (await client.delete(f"/api/models/{r.json()['id']}")).status_code == 204


async def test_trace_ingest_and_monitoring(client: httpx.AsyncClient, app: FastAPI) -> None:
    payload = {
        "name": "support-chat",
        "input": "How long do I have to return an item?",
        "output": "You can return items within 30 days. Also, our CEO personally reviews every request.",
        "context": ["Acme accepts returns within 30 days of delivery."],
        "model": "gpt-4o-mini",
        "provider": "openai",
        "latency_ms": 640,
        "input_tokens": 1000,
        "output_tokens": 100,
    }
    r = await client.post("/api/traces", json=payload)
    assert r.status_code == 202 and r.json()["score_status"] == "pending"
    trace_id = r.json()["id"]
    toxic = await client.post(
        "/api/traces",
        json={"input": "hi", "output": "You idiot, you are worthless.", "metrics": ["toxicity"]},
    )
    relevancy_only = await client.post(
        "/api/traces",
        json={
            "input": "What is 2+2?",
            "output": "It depends on several factors, so it varies overall.",
            "metrics": ["answer_relevancy"],
        },
    )
    await app.state.scorer.drain()
    assert (await client.get(f"/api/traces/{relevancy_only.json()['id']}")).json()[
        "flagged"
    ] is False

    trace = (await client.get(f"/api/traces/{trace_id}")).json()
    assert trace["score_status"] == "done"
    assert trace["cost_usd"] > 0
    scores = {s["metric"]: s for s in trace["scores"]}
    assert scores["faithfulness"]["value"] == 0.5 and scores["faithfulness"]["passed"] is False
    assert {"llm", "metric"} <= {s["kind"] for s in trace["spans"]}
    assert trace["flagged"] is True

    flagged = (
        await client.get("/api/traces", params={"source": "production", "flagged": True})
    ).json()
    assert {t["id"] for t in flagged["items"]} == {trace_id, toxic.json()["id"]}

    overview = (
        await client.get("/api/monitoring/overview", params={"window": "1h", "buckets": 6})
    ).json()
    assert overview["totals"]["traces"] == 3
    assert overview["totals"]["flagged"] == 2
    assert overview["metrics"]["toxicity"]["failures"] == 1
    assert len(overview["series"]) == 6
    assert (
        await client.get("/api/monitoring/overview", params={"window": "bogus"})
    ).status_code == 422

    bad = await client.post("/api/traces", json={"input": "a", "output": "b", "metrics": ["nope"]})
    assert bad.status_code == 422
    batch = await client.post(
        "/api/traces/batch", json=[{"input": "a", "output": "b", "metrics": []}] * 3
    )
    assert batch.status_code == 202 and all(t["score_status"] == "none" for t in batch.json())
    dup = await client.post("/api/traces", json={"id": trace_id, "input": "a", "output": "b"})
    assert dup.status_code == 409


async def test_custom_spans(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/traces",
        json={
            "input": "q",
            "output": "a",
            "metrics": [],
            "spans": [
                {"id": "retrieval0001", "name": "retrieve", "kind": "retrieval", "duration_ms": 30},
                {
                    "name": "generate",
                    "kind": "llm",
                    "parent_id": "retrieval0001",
                    "duration_ms": 200,
                },
            ],
        },
    )
    trace = (await client.get(f"/api/traces/{r.json()['id']}")).json()
    assert [s["name"] for s in trace["spans"]] == ["retrieve", "generate"]


async def test_stats(client: httpx.AsyncClient, seeded: object) -> None:
    stats = (await client.get("/api/stats")).json()
    assert stats["datasets"] == 3 and stats["models"] == 6
