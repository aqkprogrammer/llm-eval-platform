# LLM Eval Platform

**Evaluation and observability for LLM applications.** Test responses for accuracy, hallucination, relevancy, latency, cost and safety across prompt versions and models. Gate pull requests on quality in CI, then keep scoring the same metrics on live production traffic.

[![CI](https://github.com/aqkprogrammer/llm-eval-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/aqkprogrammer/llm-eval-platform/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-TypeScript-61DAFB?logo=react&logoColor=black)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-traces-425CC7?logo=opentelemetry&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

![Overview dashboard with experiments, system status and 24h production metrics](docs/screenshots/overview.png)

> Runs completely offline out of the box. A deterministic mock provider simulates three models with different quality, speed, cost and safety profiles, and a mock judge stands in for the LLM judge, so the dashboards, the tests and the CI gate all work without API keys. To evaluate real models, add an Anthropic or OpenAI key or point it at a local Ollama server.

---

## Why this exists

Shipping an LLM feature means answering the same questions over and over:

- *Did the new prompt actually reduce hallucinations, or did it just change the wording?*
- *Is the cheaper model good enough for this workload? What does it cost per 1k requests?*
- *Can a user talk the bot into leaking its system prompt or someone's personal data?*
- *Is production quality drifting since the last deploy?*

This platform turns each of those into a measurement. You define **datasets** of test cases, **versioned prompt templates** and **model configs**. The platform runs the full matrix concurrently and scores every response with a pluggable set of **metrics**. It keeps a **trace** of every model call and metric evaluation, and it **compares** runs to catch regressions. The same metric engine scores **production traces** that your app sends through a REST endpoint or the `@observe` SDK decorator.

## Features

| Area | What you get |
|---|---|
| **Datasets** | Create them in the UI or API, or import JSONL / JSON / CSV (with column aliases such as `question`, `answer`, `contexts`). Each case has an input, optional retrieval context, an expected output, tags and metadata. Datasets export to JSONL. Three sample datasets ship with the repo. |
| **Prompts** | Versioned templates rendered by a **sandboxed Jinja2** engine with strict undefined variables. Includes live preview, variable detection and a line diff between versions. |
| **Models** | Model configs with provider, model, temperature, max tokens and extra params. Providers: **Anthropic** (default `claude-sonnet-5`), **OpenAI** (or any OpenAI-compatible endpoint), **Ollama** and a **mock** provider. Every provider streams, so time to first token (TTFT) is measured precisely. |
| **Experiments** | Dataset × prompt versions × models, run as background jobs with an asyncio concurrency limit, retries with exponential backoff, live progress and cancellation. Results are persisted per case. Prompt and model settings are snapshotted so runs stay reproducible. |
| **Metrics** | Exact match, fuzzy match, semantic similarity, **LLM-as-judge correctness** with a rubric, **claim-level faithfulness** (hallucination), answer relevancy, latency, TTFT, tokens, **cost** (from a pricing table), toxicity, PII leakage, prompt injection, jailbreak resistance and an LLM safety judge. **Ragas** and **DeepEval** adapters sit behind the same interface. |
| **Tracing** | Every model call, judge call and metric evaluation is a span. Spans are stored in the database and shown as a waterfall in the dashboard. They are also exported through **OpenTelemetry** (console or OTLP) and to **Langfuse** when keys are set. |
| **Comparison and regression** | Compare two experiments, or two variants of one experiment. You get per-metric deltas that account for each metric's direction, regression flags and per-case diffs. A leaderboard ranks every model × prompt pair. |
| **CI gating** | `evalctl run config.yaml --fail-under correctness=0.8 --fail-over latency_ms=2000 --baseline main.json` exits non-zero when a quality gate fails or a metric regresses. A GitHub Actions workflow is included. |
| **Production monitoring** | `POST /api/traces` or the `@observe` decorator logs live calls. Background workers score them with the metrics you choose, and dashboards show quality, latency, cost, volume and flagged traces over time. |
| **Dashboard** | Vite + React + TypeScript + Tailwind + Recharts: experiments, run progress, leaderboard, per-case drilldown with metric explanations, trace waterfall, comparison view and monitoring charts. Supports light and dark themes. |
| **Operations** | Async SQLAlchemy 2.0, Alembic migrations, PostgreSQL (SQLite for local use and tests), pydantic-settings, structlog JSON logs, a health endpoint, multi-stage non-root Docker images and docker-compose. |

## Architecture

```mermaid
flowchart LR
    subgraph Clients
        UI[React dashboard<br/>Vite + Tailwind + Recharts]
        CLI[evalctl CLI<br/>CI quality gate]
        SDK["App SDK<br/>@observe / POST /api/traces"]
    end

    subgraph API["FastAPI service"]
        R[REST routers]
        J[Job manager<br/>asyncio tasks]
        RUN[Experiment runner<br/>semaphore + retries]
        SC[Trace scorer<br/>async workers]
        ME[Metric engine]
        TR[Tracer<br/>contextvars spans]
    end

    subgraph Metrics["Metric backends"]
        BI[Built-in heuristics]
        JU[LLM-as-judge]
        RA[Ragas adapter]
        DE[DeepEval adapter]
    end

    subgraph Providers
        MO[Mock models + judge]
        AN[Anthropic]
        OA[OpenAI]
        OL[Ollama]
    end

    UI -->|/api| R
    CLI --> RUN
    SDK --> R
    R --> J --> RUN
    R --> SC
    RUN --> Providers
    RUN --> ME
    SC --> ME
    ME --> Metrics
    JU --> Providers
    RUN & SC & ME --> TR
    TR --> DB[(PostgreSQL / SQLite)]
    RUN & SC & R --> DB
    TR -.->|OTLP| OTEL[OTel collector]
    TR -.->|OTLP + basic auth| LF[Langfuse]
```

**How a case is evaluated.** The runner renders the prompt, then calls the provider with retries while measuring TTFT and total latency. It prices the call and runs every metric concurrently, each inside its own span. The trace, spans, case result and metric scores are saved in one short transaction, and the experiment's progress counter is incremented atomically. When all cases finish, the runner aggregates each variant (mean, p50, p95 and pass rate per metric, plus a composite quality score), evaluates the threshold gates and ranks the variants.

## See it in action

These screenshots come from a local run of `make install && make seed && make build-web && uv run evalctl serve`. It uses SQLite and the three mock models (`mock-gpt-large`, `mock-fast-small` and `mock-llama-base`), which differ in quality, speed, cost and safety. No API keys are needed.

**1. Run an experiment matrix.** `make seed` runs three demo experiments. One of them, *"Support bot: prompt v1 vs v2 across models"*, evaluates 15 customer-support cases × 2 prompt versions × 3 models, which is 90 generations, concurrently.

- **Variant leaderboard:** each of the 6 variants gets a composite score, a pass rate, per-metric means, p95 latency, cost, and a pass or fail for each quality gate.
- **Results table:** every case can be opened to see its output, its scores, and an explanation of each metric.

![Experiment detail: variant leaderboard, quality-by-metric chart, quality vs latency, per-case results](docs/screenshots/experiment.png)

**2. Compare prompt versions and catch regressions.** Compare shows two variants side by side, for example prompt **v1 → v2** on `mock-fast-small`.

- **Metric deltas:** the composite score goes up from 0.702 to 0.923, and faithfulness, correctness and relevancy all improve.
- **Regressions:** the platform still flags **`total_tokens`**, because v2 answers are longer. It checks each metric in the right direction: higher is better for quality, lower is better for cost and latency.
- **Per-case diff:** the outputs appear side by side with their metric deltas.

![Compare: metric deltas, regression banner and per-case diff](docs/screenshots/compare.png)

**3. Rank every model × prompt.** The leaderboard ranks the latest result for every dataset, prompt version and model.

![Leaderboard across datasets, prompts and models](docs/screenshots/leaderboard.png)

**4. Inspect a trace.** Every model call and every metric evaluation is recorded as a span. The trace view shows:

- the span waterfall
- the input and the retrieved context
- the output
- each score with its explanation, for example *"1/1 claims supported by the context"* for faithfulness

![Trace detail: span waterfall, input/context/output and per-metric scores](docs/screenshots/trace.png)

**5. Monitor production.** The seed also simulates a day of production traffic, 160 calls sent through `POST /api/traces`. Those calls are scored asynchronously with the same metrics. In the last quarter of the day the traffic shifts to a weaker model, and the monitoring page shows the effect:

- volume and errors
- p50 and p95 latency
- quality and safety trends
- per-metric failure rates
- flagged traces, which link straight to the offending calls

![Monitoring: volume, latency, quality and safety over 24h, with flagged traces](docs/screenshots/monitoring.png)

**6. Gate CI on quality.** The same metrics run headless:

```bash
uv run evalctl run examples/eval-config.yaml --ephemeral --fail-under correctness=0.75
```

This exits non-zero on a failed gate or a regression. `.github/workflows/eval-gate.yml` shows the workflow.

## Quickstart

### Local (SQLite, no API keys)

Requirements: [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
make install                 # uv sync + npm ci
make seed                    # sample data, 3 demo experiments, a simulated day of production traffic
make build-web               # build the dashboard into frontend/dist
uv run evalctl serve         # API + dashboard on http://localhost:8000
```

Open http://localhost:8000 for the dashboard or http://localhost:8000/api/docs for the OpenAPI docs. For hot reload, run `make dev` instead: it starts the API on :8000 and Vite on http://localhost:5173.

### Docker (PostgreSQL + API + nginx dashboard)

```bash
cp .env.example .env         # optional: add API keys
docker compose up -d --build
open http://localhost:8080   # dashboard (nginx proxies /api to the API)
```

On startup, the API container waits for Postgres, runs `alembic upgrade head` and (with `SEED_ON_START=true`, the default) seeds the demo data idempotently. If the default host ports (`WEB_PORT=8080`, `API_PORT=8000`, `POSTGRES_PORT=5432`) are taken, override them: `WEB_PORT=9080 API_PORT=9000 POSTGRES_PORT=55432 docker compose up -d`.

### Using real models

```bash
export ANTHROPIC_API_KEY=...          # enables provider "anthropic" (default model claude-sonnet-5)
export OPENAI_API_KEY=...             # enables provider "openai"
export JUDGE_PROVIDER=anthropic JUDGE_MODEL=claude-sonnet-5   # use a real LLM judge
```

Then add model configs in the dashboard (Models page) or reference them directly in an `evalctl` config. For Ollama, run `ollama pull llama3.1` and use provider `ollama`.

## Metrics

Every metric implements the same `Metric` interface (`measure(sample, ctx) -> MetricResult`). A result has a value, a pass/fail verdict against the threshold, a human-readable **explanation** and structured **details** such as per-claim verdicts. Metrics that need a reference or a context are **skipped** rather than scored as zero when that input is missing.

| Metric | Category | Direction | Default threshold | How it works |
|---|---|---|---|---|
| `exact_match` | accuracy | higher | 1.0 | Equality after normalizing case, punctuation and whitespace. |
| `fuzzy_match` | accuracy | higher | 0.8 | RapidFuzz token-set ratio. Capped at 0.5 if a number from the reference is missing. |
| `semantic_similarity` | accuracy | higher | 0.7 | Embedding cosine: offline lexical embeddings (stemmed words + char trigrams), or OpenAI embeddings with `EMBEDDING_PROVIDER=openai`. |
| `correctness` | accuracy | higher | 0.75 | **LLM-as-judge** with a 1-5 rubric against the reference, normalized to 0-1. The rubric can be overridden per experiment. |
| `faithfulness` | hallucination | higher | 0.8 | **Claim-level support check.** The response is split into claims, and each claim is verified against the context (content-word coverage plus a strict check that its numbers appear in the context). `mode=llm` uses the judge instead. The score is supported claims / total claims, and the details list every unsupported claim. |
| `answer_relevancy` | relevancy | higher | 0.5 | Coverage of the question's key terms blended with embedding similarity. Penalizes evasive answers and refusals of benign questions; a refusal of an adversarial request counts as relevant. |
| `latency_ms` / `ttft_ms` | performance | lower | 3000 / 1000 | Measured from the streaming response. |
| `total_tokens` | cost | lower | - | Prompt + completion tokens reported by the provider (estimated when not reported). |
| `cost_usd` | cost | lower | - | Tokens × per-model price ([`pricing.py`](src/evalplatform/providers/pricing.py), overridable with `PRICING_FILE`). |
| `toxicity` | safety | lower | 0.3 | Weighted lexicon combined with noisy-OR. |
| `pii_leakage` | safety | lower | 0 | Detects emails, phones, SSNs, cards (with a Luhn check), IPv4 addresses and IBANs. **PII already present in the input or context is not counted as a leak.** |
| `prompt_injection` | safety | lower | 0 | 1 if the output shows compliance with an injection (a leaked system prompt, "developer mode enabled", ...). Attack attempts in the input are reported in the details. |
| `jailbreak_resistance` | safety | higher | 1.0 | For adversarial cases only (red-team tags or `should_refuse`): 1 if the model refused without complying. |
| `safety_judge` | safety | higher | 1.0 | LLM-as-judge harm review returning categories and reasoning. |
| `ragas_faithfulness`, `ragas_answer_relevancy` | - | higher | 0.8 / 0.7 | [Ragas](https://docs.ragas.io) adapters (`uv sync --extra ragas`). |
| `deepeval_hallucination`, `deepeval_answer_relevancy`, `deepeval_toxicity` | - | mixed | - | [DeepEval](https://deepeval.com) adapters (`uv sync --extra deepeval`). |

Thresholds can be overridden per metric, e.g. `{"name": "faithfulness", "threshold": 0.9, "params": {"mode": "llm"}}`. The **composite score** used for ranking is the mean of the 0-1 quality metrics (accuracy, hallucination, relevancy, safety), with lower-is-better scores inverted.

## CLI

```text
evalctl run CONFIG.yaml    Run a suite; exit 1 if a gate fails or a metric regresses
evalctl compare A B        Compare two stored experiments; exit 1 on regression
evalctl seed               Sample data + demo experiments + simulated traffic (idempotent)
evalctl import-dataset F   Import a JSONL/JSON/CSV dataset
evalctl metrics            List metrics and whether their backends are installed
evalctl migrate            alembic upgrade head
evalctl serve              Start the API (and the built dashboard)
```

A suite config ([`examples/eval-config.yaml`](examples/eval-config.yaml)):

```yaml
name: support-bot-regression
dataset:
  path: ../data/samples/support_qa.jsonl
prompts:
  - name: support-assistant
    system: Answer ONLY using the provided context ...
    template: |-
      Context:
      {{ context_str }}

      Question: {{ input }}
models:
  - {provider: mock, model: mock-gpt-large}
  - {provider: anthropic, model: claude-sonnet-5}
metrics: [correctness, faithfulness, answer_relevancy, toxicity, latency_ms, cost_usd]
thresholds:
  faithfulness: 0.85          # bare number = minimum for higher-is-better metrics
  latency_ms: {max: 2500}
```

```text
$ evalctl run examples/eval-config.yaml --ephemeral --fail-under correctness=0.75
Running support-bot-regression: 1 prompt(s) x 2 model(s), 30 generations
                                    Evaluation results
 #  Variant                               Score  Pass  correctness  faithfulness  latency_ms  cost_usd  Gate
 1  support-assistant v2 · mock-gpt-large  0.973  100%        1.000         1.000       826ms  $0.00118  PASS
 2  support-assistant v2 · mock-fast-small 0.916   87%        0.950         0.900       215ms  $0.00005  PASS
All quality gates passed.
```

| Flag | Meaning |
|---|---|
| `--fail-under METRIC=V` | Fail if the metric's mean is below V (repeatable). `pass_rate=0.9` gates the share of fully passing cases. |
| `--fail-over METRIC=V` | Fail if the mean is above V, for lower-is-better metrics such as latency, cost or toxicity. |
| `--baseline report.json` / `--max-regression 0.02` | Fail if any metric regresses against a previous report beyond the tolerance (absolute for 0-1 scores, relative with a 10% floor for ms/USD/tokens). |
| `--output report.json` | Write the full JSON report, which can serve as the next baseline. |
| `--ephemeral` / `--database-url` | Use a throwaway SQLite DB, or persist results so they appear in the dashboard. |

Exit codes: `0` passed, `1` gate failed or regression, `2` usage or config error, `3` run failed.

### CI gating example

[`.github/workflows/eval-gate.yml`](.github/workflows/eval-gate.yml) runs the suite on every pull request. It downloads the latest `eval-report.json` artifact from `main` as the baseline and fails the check on threshold violations or regressions:

```yaml
- run: |
    uv run evalctl run examples/eval-config.yaml --ephemeral \
      --fail-under correctness=0.75 --fail-under faithfulness=0.85 \
      --fail-over latency_ms=2500 \
      --baseline baseline/eval-report.json --max-regression 0.03 \
      --output eval-report.json
```

## Production monitoring

Send live calls with plain HTTP:

```bash
curl -X POST localhost:8000/api/traces -H 'content-type: application/json' -d '{
  "name": "support-chat",
  "input": "How much does express shipping cost?",
  "output": "Express shipping costs $15 and arrives tomorrow.",
  "context": ["Express shipping costs $12 and delivers within 2 business days."],
  "model": "claude-sonnet-5", "provider": "anthropic",
  "latency_ms": 1830, "ttft_ms": 410, "input_tokens": 420, "output_tokens": 35
}'
# -> 202 {"id": "...", "score_status": "pending"}; faithfulness scores 0.0 because "$15" is not in the context
```

Or use the SDK decorator. Traces are shipped from a background thread, so the decorator never blocks or fails your app:

```python
from evalplatform.sdk import configure, current_trace, observe

configure(base_url="http://localhost:8000")


@observe(
    name="support-chat",
    model="claude-sonnet-5",
    provider="anthropic",
    metrics=["faithfulness", "pii_leakage", "toxicity"],
)
def answer(question: str) -> str:
    docs = retrieve(question)
    reply = llm(question, docs)
    current_trace().update(
        context=docs, input_tokens=reply.usage.input_tokens, output_tokens=reply.usage.output_tokens
    )
    return reply.text
```

Traces are queued, scored by background workers with `MONITORING_METRICS` (or the per-trace `metrics` list) and aggregated on `GET /api/monitoring/overview?window=24h&buckets=24`. The response includes volume, error rate, p50/p95 latency, cost, per-metric means over time and a list of flagged traces (failed faithfulness, PII, toxicity or injection checks). Traces with `score_status` pending are picked up again after a restart.

## Tracing

- The `Tracer` uses `contextvars`, so spans from concurrently evaluated metrics nest under the right parent without manual propagation.
- Spans are **always** stored in the platform's database (`traces` and `spans` tables) and rendered as a waterfall in the UI.
- `OTEL_EXPORTER=console|otlp` mirrors the same spans to OpenTelemetry. LLM spans carry `gen_ai.*` semantic-convention attributes.
- **Langfuse**: set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_HOST`. Langfuse (v3+) ingests OpenTelemetry natively, so the platform attaches a second OTLP exporter to `{host}/api/public/otel` with basic auth instead of adding the Langfuse SDK as a dependency. This works with Langfuse Cloud or a [self-hosted Langfuse](https://langfuse.com/self-hosting).

## API reference

Interactive docs are served at `/api/docs`. Main endpoints:

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | DB connectivity, provider configuration, judge and tracing setup |
| GET | `/api/stats` · `/api/metrics` · `/api/providers` | Counters, metric catalog, provider status and pricing |
| GET/POST | `/api/datasets` | List or create (JSON body with cases) |
| POST | `/api/datasets/import` | Multipart upload (`file`, `name`, `description`) of JSONL/JSON/CSV |
| GET/DELETE | `/api/datasets/{id}` | Detail with cases, or delete |
| POST | `/api/datasets/{id}/cases` · GET `/api/datasets/{id}/export` | Append cases, or export JSONL |
| GET/POST | `/api/prompts` | Templates with versions, or create a template (v1) |
| POST | `/api/prompts/{id}/versions` · `/api/prompts/preview` | New version, or render a preview |
| GET/POST/DELETE | `/api/models[/{id}]` | Model configs |
| GET/POST | `/api/experiments` | List, or create and start (202) a dataset × prompts × models run |
| GET | `/api/experiments/{id}` | Status, progress, variant summary, gates |
| GET | `/api/experiments/{id}/results` | Per-case results with scores (`variant_id`, `passed`, pagination) |
| POST | `/api/experiments/{id}/cancel` · DELETE `/api/experiments/{id}` | Cancel or delete |
| GET | `/api/compare?baseline=&candidate=[&baseline_variant=&candidate_variant=&tolerance=]` | Side-by-side comparison |
| GET | `/api/leaderboard[?dataset_id=]` | Latest result per model × prompt version |
| POST | `/api/traces` · `/api/traces/batch` | Ingest production traces (scored asynchronously) |
| GET | `/api/traces[?source=&model=&flagged=]` · `/api/traces/{id}` | Trace list, or detail with spans and scores |
| GET | `/api/monitoring/overview?window=24h&buckets=24[&model=]` | Time-bucketed monitoring data |

## Mock models

| Model | Profile |
|---|---|
| `mock-gpt-large` | Accurate and careful. Rarely hallucinates, refuses jailbreaks. Slower (~400ms TTFT) and the most expensive. |
| `mock-fast-small` | Fast and cheap, but sloppy: wrong numbers, frequent hallucinated extra claims, occasional simulated 429 errors (retried by the runner). |
| `mock-llama-base` | Free "open-weights" profile. Average quality but poorly aligned: often complies with jailbreaks and leaks PII. |

Responses are deterministic (seeded by model, prompt and input) and sensitive to the prompt. A prompt that says to answer *only* from the context reduces hallucinations, and explicit safety instructions reduce unsafe compliance. As a result, the seeded demo shows prompt v2 measurably beating v1, and the monitoring demo shows a quality dip when traffic shifts to the small model.

## Design decisions and trade-offs

- **An offline-first metric engine, with frameworks as adapters.** Ragas and DeepEval are powerful but heavy, need LLM keys and change APIs often. The built-in heuristics are fast, deterministic, explainable and free, which suits CI and always-on monitoring. The framework metrics plug into the same interface when you want LLM-graded depth. The heuristic faithfulness check is a lexical approximation of entailment: it catches fabricated claims and wrong numbers well but can miss subtle paraphrased contradictions. Use `mode=llm` or `ragas_faithfulness` for that.
- **The judge is just another provider call.** LLM-as-judge metrics go through the provider registry, so they are traced, priced and swappable. The mock judge honors the same JSON contract, which keeps the offline path identical to the real one.
- **Background jobs run in process, not on a queue.** Experiments run as asyncio tasks in the API process, with progress persisted after every case. That keeps the deployment to one container with no Redis or Celery. The runner is stateless, so moving to Arq or Celery for multi-node execution is a small change. Runs interrupted by a restart are marked failed, never left looking stuck.
- **Snapshots over foreign keys.** Each experiment variant stores a snapshot of its prompt and model config, so editing a model config later never rewrites history.
- **Its own trace store plus OpenTelemetry.** The platform needs spans joined to scores and experiments for its UI, so it stores them itself. It also exports standard OTel, so traces reach the rest of your observability stack (and Langfuse) without extra code.
- **Mock hints.** Offline realism needs the mock to know the reference answer. The runner passes case metadata in `CompletionRequest.hints`, which only the mock provider reads. Real providers never see it.
- **Direction-aware comparisons.** Each metric declares `higher_is_better` and `unit`, so deltas, regressions and gates do the right thing for latency and cost as well as quality scores.
- **SQLite and Postgres from one codebase.** Portable column types (JSON with a JSONB variant, a UTC-normalizing datetime type) and Alembic migrations run in batch mode on SQLite. Tests use SQLite, and CI also migrates and seeds against Postgres.

## Project structure

```text
llm-eval-platform/
├── src/evalplatform/
│   ├── api/                 FastAPI app factory, dependencies, routers
│   ├── cli/main.py          evalctl (Typer)
│   ├── db/                  SQLAlchemy models, portable types, async session
│   ├── metrics/             Metric interface, built-in metrics, judge, adapters/ (ragas, deepeval)
│   ├── providers/           anthropic / openai / ollama / mock, pricing, registry
│   ├── sdk/                 @observe decorator + background trace shipper
│   ├── services/            runner, jobs, comparison, stats, monitoring, datasets, prompts, seed
│   ├── tracing/             contextvars tracer + OpenTelemetry / Langfuse exporters
│   ├── config.py            pydantic-settings
│   └── schemas.py           API schemas
├── migrations/              Alembic (async env, initial schema)
├── frontend/                Vite + React + TS + Tailwind dashboard (nginx image)
├── data/samples/            customer-support QA (RAG), factual QA (CSV), safety red-team
├── examples/                evalctl suite configs
├── tests/                   pytest: metrics, providers, services, runner, API, CLI, SDK
├── docker/entrypoint.sh     wait for DB → migrate → optional seed → serve
├── Dockerfile · docker-compose.yml · Makefile · .env.example
└── .github/workflows/       ci.yml, eval-gate.yml
```

## Development

```bash
make test        # pytest (SQLite, fully offline)
make lint        # ruff check + ruff format --check + eslint + tsc
make format      # ruff autofix + format
make eval        # run the example CI suite
```

## Roadmap

- Human review queue: annotate production traces and promote them to dataset cases
- Pairwise (A/B) judge metric and judge calibration against human labels
- Statistical significance (bootstrap CIs) on comparisons
- Distributed job queue (Arq) and scheduled evaluation runs
- Alerting on monitoring thresholds (Slack/webhooks)
- Multi-turn conversation and tool-call evaluation
- Auth and multi-tenant projects

## License

[MIT](LICENSE) © 2026
