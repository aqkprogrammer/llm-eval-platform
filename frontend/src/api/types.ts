// Types mirror the real responses of the FastAPI backend (see /api/openapi.json).

export type ISODate = string;

export type MetricUnit = "score" | "ms" | "usd" | "tokens" | "count";
export type MetricCategory =
  | "accuracy"
  | "relevancy"
  | "hallucination"
  | "safety"
  | "performance"
  | "cost"
  | (string & {});

export type ExperimentStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | (string & {});
export type ProviderName = "mock" | "anthropic" | "openai" | "ollama";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ------------------------------------------------------------------ system
export interface Health {
  status: "ok" | "degraded";
  version: string;
  database: { ok: boolean; dialect: string };
  providers: Record<string, boolean>;
  judge: { provider: string; model: string };
  tracing: { otel_exporter: string; langfuse: boolean };
}

export interface Stats {
  datasets: number;
  prompts: number;
  models: number;
  experiments: number;
  experiments_running: number;
  traces_production: number;
  traces_total: number;
}

export interface MetricInfo {
  name: string;
  category: MetricCategory;
  description: string;
  higher_is_better: boolean;
  unit: MetricUnit;
  requires: string[];
  default_threshold: number | null;
  uses_llm: boolean;
  backend: string;
  available: boolean;
}

// ------------------------------------------------------------------ datasets
export interface TestCase {
  id: string;
  position: number;
  input: string;
  context: string[];
  expected_output: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface DatasetSummary {
  id: string;
  name: string;
  description: string;
  tags: string[];
  created_at: ISODate;
  case_count: number;
}

export interface Dataset extends DatasetSummary {
  cases: TestCase[];
}

// ------------------------------------------------------------------ prompts
export interface PromptVersion {
  id: string;
  template_id: string;
  version: number;
  system_prompt: string;
  user_template: string;
  notes: string;
  created_at: ISODate;
  variables: string[];
}

export interface PromptTemplate {
  id: string;
  name: string;
  description: string;
  created_at: ISODate;
  versions: PromptVersion[];
}

export interface PromptVersionCreate {
  system_prompt: string;
  user_template: string;
  notes: string;
}

export interface PromptTemplateCreate extends PromptVersionCreate {
  name: string;
  description: string;
}

export interface PromptPreviewRequest {
  system_prompt: string;
  user_template: string;
  input: string;
  context: string[];
}

export interface PromptPreview {
  system: string;
  user: string;
  variables: string[];
}

// ------------------------------------------------------------------ models
export interface ModelConfig {
  id: string;
  name: string;
  provider: ProviderName | (string & {});
  model: string;
  temperature: number | null;
  max_tokens: number;
  params: Record<string, unknown>;
  created_at: ISODate;
  available: boolean;
}

export interface ModelConfigCreate {
  name: string;
  provider: ProviderName;
  model: string;
  temperature: number | null;
  max_tokens: number;
  params: Record<string, unknown>;
}

export interface ProvidersResponse {
  providers: { name: string; configured: boolean }[];
  pricing: Record<string, { input: number; output: number }>;
}

// ------------------------------------------------------------------ experiments
export interface MetricAggregate {
  higher_is_better: boolean;
  unit: MetricUnit;
  category: MetricCategory;
  n: number;
  skipped: number;
  mean: number | null;
  p50: number | null;
  p95: number | null;
  min: number | null;
  max: number | null;
  sum: number | null;
  pass_rate: number | null;
}

export interface Gate {
  metric: string;
  actual: number | null;
  min?: number;
  max?: number;
  passed: boolean;
}

export interface VariantSummary {
  variant_id: string;
  label: string;
  model: string;
  provider: string;
  model_config_name: string;
  prompt: string;
  prompt_version: number;
  cases: number;
  errors: number;
  pass_rate: number | null;
  total_cost_usd: number;
  composite_score: number | null;
  metrics: Record<string, MetricAggregate>;
  gates: Gate[];
  gate_passed: boolean;
  rank: number;
}

export interface ExperimentSummaryData {
  variants?: VariantSummary[];
  gate_passed?: boolean;
  best_variant_id?: string | null;
}

export interface Variant {
  id: string;
  label: string;
  prompt_version_id: string | null;
  model_config_id: string | null;
  prompt_snapshot: Record<string, unknown>;
  model_snapshot: Record<string, unknown>;
}

export interface ExperimentSummary {
  id: string;
  name: string;
  description: string;
  dataset_id: string;
  dataset_name: string | null;
  status: ExperimentStatus;
  source: string;
  progress_total: number;
  progress_done: number;
  progress_failed: number;
  created_at: ISODate;
  started_at: ISODate | null;
  finished_at: ISODate | null;
  error: string | null;
  variant_count: number;
  gate_passed: boolean | null;
}

export interface MetricSpec {
  name: string;
  threshold: number | null;
  params: Record<string, unknown>;
}

export interface Experiment extends ExperimentSummary {
  metrics: MetricSpec[];
  thresholds: Record<string, number | { min?: number; max?: number }>;
  concurrency: number;
  summary: ExperimentSummaryData;
  variants: Variant[];
}

export interface ExperimentCreate {
  name: string;
  description?: string;
  dataset_id: string;
  prompt_version_ids: string[];
  model_config_ids: string[];
  metrics?: string[];
  thresholds?: Record<string, number>;
  concurrency?: number | null;
  case_limit?: number | null;
}

export interface MetricScore {
  metric: string;
  category: MetricCategory;
  value: number | null;
  passed: boolean | null;
  explanation: string;
  details: Record<string, unknown>;
  error: string | null;
}

export interface CaseResult {
  id: string;
  variant_id: string;
  test_case_id: string;
  input: string;
  expected_output: string | null;
  context: string[];
  tags: string[];
  rendered_prompt: string;
  output: string | null;
  error: string | null;
  latency_ms: number | null;
  ttft_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  passed: boolean | null;
  trace_id: string | null;
  scores: MetricScore[];
}

// ------------------------------------------------------------------ comparison
export type DeltaStatus = "improved" | "regressed" | "unchanged" | "missing";

export interface CompareSide {
  experiment_id: string;
  variant_id: string | null;
  label: string;
  composite_score: number | null;
  cases: number;
}

export interface CompareMetric {
  metric: string;
  higher_is_better: boolean;
  unit: MetricUnit;
  category: MetricCategory;
  baseline: number | null;
  candidate: number | null;
  baseline_pass_rate: number | null;
  candidate_pass_rate: number | null;
  delta: number | null;
  status: DeltaStatus;
}

export type CaseDiffStatus = "improved" | "regressed" | "mixed" | "unchanged";

export interface CompareCase {
  test_case_id: string;
  input: string;
  expected_output: string | null;
  baseline_output: string | null;
  candidate_output: string | null;
  baseline_passed: boolean | null;
  candidate_passed: boolean | null;
  baseline_metrics: Record<string, number | null>;
  candidate_metrics: Record<string, number | null>;
  deltas: Record<string, number | null>;
  regressed_metrics: string[];
  improved_metrics: string[];
  status: CaseDiffStatus;
}

export interface Comparison {
  baseline: CompareSide;
  candidate: CompareSide;
  same_dataset: boolean;
  tolerance: number;
  metrics: CompareMetric[];
  regressions: string[];
  has_regression: boolean;
  case_summary: Record<CaseDiffStatus, number>;
  cases: CompareCase[];
}

// ------------------------------------------------------------------ leaderboard
export interface LeaderboardRow {
  dataset_id: string;
  dataset_name: string;
  experiment_id: string;
  experiment_name: string;
  variant_id: string;
  label: string;
  model: string;
  model_config_name: string;
  provider: string;
  prompt: string;
  prompt_version: number;
  composite_score: number | null;
  pass_rate: number | null;
  total_cost_usd: number | null;
  cases: number;
  metrics: Record<string, number | null>;
  latency_p95: number | null;
  finished_at: ISODate | null;
}

// ------------------------------------------------------------------ traces
export type ScoreStatus = "pending" | "running" | "done" | "failed" | "skipped" | (string & {});

export interface TraceSummary {
  id: string;
  name: string;
  source: "production" | "experiment" | (string & {});
  experiment_id: string | null;
  status: string;
  provider: string | null;
  model: string | null;
  latency_ms: number | null;
  ttft_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  score_status: ScoreStatus;
  start_time: ISODate;
  input_preview: string;
  output_preview: string;
  tags: string[];
  flagged: boolean;
}

export interface Span {
  id: string;
  trace_id: string;
  parent_id: string | null;
  name: string;
  kind: "llm" | "metric" | "chain" | "internal" | (string & {});
  status: string;
  start_time: ISODate;
  end_time: ISODate | null;
  duration_ms: number | null;
  attributes: Record<string, unknown>;
  error: string | null;
}

export interface Trace extends TraceSummary {
  input: string | null;
  output: string | null;
  context: string[];
  user_id: string | null;
  session_id: string | null;
  metadata: Record<string, unknown>;
  end_time: ISODate | null;
  spans: Span[];
  scores: MetricScore[];
}

// ------------------------------------------------------------------ monitoring
export interface MonitoringBucket {
  ts: ISODate;
  count: number;
  errors: number;
  cost_usd: number | null;
  latency_p50: number | null;
  latency_p95: number | null;
  [metric: string]: number | string | null;
}

export interface MonitoringOverview {
  window: string;
  from: ISODate;
  to: ISODate;
  totals: {
    traces: number;
    errors: number;
    error_rate: number;
    cost_usd: number;
    latency_p50: number | null;
    latency_p95: number | null;
    flagged: number;
    pending_scoring: number;
  };
  metrics: Record<string, { mean: number | null; n: number; failures: number }>;
  models: Record<string, number>;
  series: MonitoringBucket[];
  flagged: {
    id: string;
    name: string;
    model: string | null;
    start_time: ISODate;
    input_preview: string;
    failed_metrics: string[];
  }[];
}
