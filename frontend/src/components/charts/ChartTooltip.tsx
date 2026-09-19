import type { ReactNode } from "react";

export interface TooltipItem {
  name?: string | number;
  value?: unknown;
  color?: string;
  fill?: string;
  stroke?: string;
  dataKey?: unknown;
  payload?: unknown;
}

export function ChartTooltip({
  active,
  payload,
  label,
  valueFormatter,
  labelFormatter,
}: {
  active?: boolean;
  payload?: readonly TooltipItem[];
  label?: unknown;
  valueFormatter?: (v: number, name: string) => string;
  labelFormatter?: (label: unknown, payload: readonly TooltipItem[]) => ReactNode;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-36 rounded-md border border-zinc-200 bg-white/95 px-2.5 py-2 text-xs shadow-lg backdrop-blur dark:border-zinc-700 dark:bg-zinc-900/95">
      {label !== undefined && label !== null && label !== "" && (
        <div className="mb-1.5 font-medium text-zinc-900 dark:text-zinc-100">
          {labelFormatter ? labelFormatter(label, payload) : String(label)}
        </div>
      )}
      <div className="space-y-1">
        {payload.map((p, i) => {
          const name = String(p.name ?? p.dataKey ?? "");
          const v = p.value;
          const text =
            typeof v === "number" ? (valueFormatter ? valueFormatter(v, name) : v.toLocaleString()) : v == null ? "—" : String(v);
          return (
            <div key={`${name}-${i}`} className="flex items-center justify-between gap-4">
              <span className="flex min-w-0 items-center gap-1.5 text-zinc-600 dark:text-zinc-400">
                <span
                  className="size-2 shrink-0 rounded-sm"
                  style={{ background: p.color ?? p.stroke ?? p.fill ?? "var(--chart-1)" }}
                />
                <span className="truncate">{name}</span>
              </span>
              <span className="tabular font-mono font-medium text-zinc-900 dark:text-zinc-100">{text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ChartLegend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          {it.dashed ? (
            <span className="h-0 w-3 border-t-2 border-dashed" style={{ borderColor: it.color }} />
          ) : (
            <span className="size-2.5 rounded-sm" style={{ background: it.color }} />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}
