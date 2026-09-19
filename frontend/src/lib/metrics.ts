import type { MetricCategory } from "../api/types";

export const DEFAULT_METRICS = [
  "correctness",
  "semantic_similarity",
  "faithfulness",
  "answer_relevancy",
  "toxicity",
  "pii_leakage",
  "prompt_injection",
  "jailbreak_resistance",
  "latency_ms",
  "ttft_ms",
  "total_tokens",
  "cost_usd",
];

export const CATEGORY_ORDER: MetricCategory[] = [
  "accuracy",
  "relevancy",
  "hallucination",
  "safety",
  "performance",
  "cost",
];

export const QUALITY_CATEGORIES = new Set(["accuracy", "relevancy", "hallucination", "safety"]);

export const CATEGORY_LABEL: Record<string, string> = {
  accuracy: "Accuracy",
  relevancy: "Relevancy",
  hallucination: "Hallucination",
  safety: "Safety",
  performance: "Performance",
  cost: "Cost",
};

export const categoryRank = (c: string) => {
  const i = CATEGORY_ORDER.indexOf(c);
  return i === -1 ? CATEGORY_ORDER.length : i;
};

/** Categorical chart colours (CSS variables, theme-aware), assigned in fixed order. */
export const SERIES_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-8)",
];

export const seriesColor = (i: number) => SERIES_COLORS[i % SERIES_COLORS.length];

/** Whether a delta is good given the metric direction. */
export function deltaTone(delta: number | null | undefined, higherIsBetter: boolean, eps = 1e-9) {
  if (delta === null || delta === undefined || Math.abs(delta) < eps) return "neutral" as const;
  return (delta > 0) === higherIsBetter ? ("good" as const) : ("bad" as const);
}
