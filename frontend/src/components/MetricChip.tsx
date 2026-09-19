import { cn } from "../lib/cn";
import { fmtMetric } from "../lib/format";

export function MetricChip({
  name,
  value,
  passed,
  unit,
}: {
  name: string;
  value: number | null;
  passed: boolean | null;
  unit?: string;
}) {
  return (
    <span
      title={`${name}: ${fmtMetric(value, unit)}${passed === null ? "" : passed ? " (pass)" : " (fail)"}`}
      className={cn(
        "tabular inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-inset",
        passed === true && "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/20",
        passed === false && "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:ring-rose-500/20",
        passed === null && "bg-zinc-50 text-zinc-600 ring-zinc-200 dark:bg-zinc-800/50 dark:text-zinc-400 dark:ring-zinc-700/50",
      )}
    >
      <span className="font-sans text-[10px] opacity-75">{name}</span>
      {fmtMetric(value, unit)}
    </span>
  );
}

/** Horizontal 0-1 score bar with numeric label. */
export function ScoreBar({ value, className }: { value: number | null | undefined; className?: string }) {
  const v = typeof value === "number" ? Math.max(0, Math.min(1, value)) : null;
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
        {v !== null && (
          <div
            className={cn(
              "h-full rounded-full",
              v >= 0.8 ? "bg-emerald-500" : v >= 0.6 ? "bg-amber-500" : "bg-rose-500",
            )}
            style={{ width: `${v * 100}%` }}
          />
        )}
      </div>
      <span className="tabular font-mono text-xs">{v === null ? "—" : v.toFixed(3)}</span>
    </div>
  );
}
