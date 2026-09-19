import { useMemo } from "react";
import { useMetrics } from "../api/queries";
import type { MetricInfo } from "../api/types";

/** Map of metric name to its registry info (unit, direction, category). */
export function useMetricIndex(): Map<string, MetricInfo> {
  const { data } = useMetrics();
  return useMemo(() => new Map((data ?? []).map((m) => [m.name, m])), [data]);
}
