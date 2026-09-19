export const axisTick = { fill: "var(--chart-axis)", fontSize: 11 };

export const xAxisProps = {
  tick: axisTick,
  tickLine: false,
  axisLine: { stroke: "var(--chart-grid)" },
  tickMargin: 6,
} as const;

export const yAxisProps = {
  tick: axisTick,
  tickLine: false,
  axisLine: false,
  width: 44,
} as const;

export const gridProps = {
  stroke: "var(--chart-grid)",
  strokeDasharray: "0",
  vertical: false,
} as const;

export const cursorFill = { fill: "var(--chart-grid)", fillOpacity: 0.45 };
export const cursorLine = { stroke: "var(--chart-axis)", strokeWidth: 1, strokeDasharray: "3 3" };

export function timeTick(iso: string, window: string): string {
  const d = new Date(iso);
  if (window.endsWith("d")) return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}
