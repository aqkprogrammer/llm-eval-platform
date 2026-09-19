from __future__ import annotations

from typing import Any

import httpx


async def catalog(client: httpx.AsyncClient) -> dict[str, Any]:
    datasets = {d["name"]: d for d in (await client.get("/api/datasets")).json()}
    prompts = {p["name"]: p for p in (await client.get("/api/prompts")).json()}
    models = {m["name"]: m for m in (await client.get("/api/models")).json()}
    return {"datasets": datasets, "prompts": prompts, "models": models}


def experiment_payload(cat: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload = {
        "name": "test run",
        "dataset_id": cat["datasets"]["customer-support-qa"]["id"],
        "prompt_version_ids": [v["id"] for v in cat["prompts"]["support-assistant"]["versions"]],
        "model_config_ids": [
            cat["models"]["mock-gpt-large"]["id"],
            cat["models"]["mock-fast-small"]["id"],
        ],
        "metrics": [
            "correctness",
            "faithfulness",
            "answer_relevancy",
            "toxicity",
            "latency_ms",
            "cost_usd",
        ],
        "thresholds": {"faithfulness": 0.7},
        "case_limit": 6,
    }
    payload.update(overrides)
    return payload
