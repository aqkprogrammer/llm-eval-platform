import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Span } from "../../api/types";
import { cn } from "../../lib/cn";
import { fmtMs, fmtSpan } from "../../lib/format";
import { ChartLegend } from "../charts/ChartTooltip";
import { Badge } from "../ui/Badge";
import { JsonView } from "../ui/CodeBlock";

/** Parse an ISO timestamp to microseconds, keeping sub-millisecond precision that Date drops. */
function toMicros(iso: string): number {
  const m = /^(.*T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$/.exec(iso);
  if (!m) return Date.parse(iso) * 1000;
  const base = Date.parse(`${m[1]}${m[3] ?? "Z"}`) * 1000;
  const frac = (m[2] ?? "").padEnd(6, "0").slice(0, 6);
  return base + Number(frac);
}

const KIND_COLOR: Record<string, string> = {
  llm: "var(--chart-7)",
  chain: "var(--chart-1)",
  metric: "var(--chart-3)",
  internal: "var(--chart-muted)",
};
const ERROR_COLOR = "var(--chart-bad)";

interface Row {
  span: Span;
  depth: number;
  start: number;
  end: number;
  hasChildren: boolean;
  ancestors: string[];
}

function buildRows(spans: Span[]): { rows: Row[]; t0: number; total: number } {
  const byId = new Map(spans.map((s) => [s.id, s]));
  const children = new Map<string, Span[]>();
  const roots: Span[] = [];
  for (const s of spans) {
    if (s.parent_id && byId.has(s.parent_id)) {
      const list = children.get(s.parent_id) ?? [];
      list.push(s);
      children.set(s.parent_id, list);
    } else {
      roots.push(s);
    }
  }
  const timing = (s: Span) => {
    const start = toMicros(s.start_time);
    const end = s.end_time
      ? toMicros(s.end_time)
      : start + Math.round((s.duration_ms ?? 0) * 1000);
    return { start, end: Math.max(end, start) };
  };
  const byStart = (a: Span, b: Span) => toMicros(a.start_time) - toMicros(b.start_time);
  const rows: Row[] = [];
  const visit = (s: Span, depth: number, ancestors: string[]) => {
    const kids = (children.get(s.id) ?? []).sort(byStart);
    rows.push({ span: s, depth, ...timing(s), hasChildren: kids.length > 0, ancestors });
    for (const k of kids) visit(k, depth + 1, [...ancestors, s.id]);
  };
  roots.sort(byStart).forEach((r) => visit(r, 0, []));
  const t0 = Math.min(...rows.map((r) => r.start));
  const t1 = Math.max(...rows.map((r) => r.end));
  return { rows, t0, total: Math.max(t1 - t0, 1) };
}

export function Waterfall({ spans }: { spans: Span[] }) {
  const { rows, t0, total } = useMemo(() => buildRows(spans), [spans]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = rows.find((r) => r.span.id === selectedId)?.span ?? null;
  const visible = rows.filter((r) => !r.ancestors.some((a) => collapsed.has(a)));
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const kinds = [...new Set(spans.map((s) => s.kind))];

  if (!rows.length) return <p className="p-4 text-sm text-zinc-500">No spans recorded for this trace.</p>;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
        <ChartLegend
          items={[
            ...kinds.map((k) => ({ label: k, color: KIND_COLOR[k] ?? KIND_COLOR.internal })),
            ...(spans.some((s) => s.status === "error") ? [{ label: "error", color: ERROR_COLOR }] : []),
          ]}
        />
        <span className="tabular text-xs text-zinc-500">
          {rows.length} spans, {fmtSpan(total / 1000)} total
        </span>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[640px] px-4 py-3">
          <div className="grid grid-cols-[minmax(220px,34%)_1fr] border-b border-zinc-200 pb-1.5 text-[10px] text-zinc-400 dark:border-zinc-800">
            <span className="font-medium tracking-wide uppercase">Span</span>
            <div className="relative h-3">
              {ticks.map((t) => (
                <span
                  key={t}
                  className="tabular absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full"
                  style={{ left: `${t * 100}%` }}
                >
                  {fmtSpan((total * t) / 1000)}
                </span>
              ))}
            </div>
          </div>
          <ul role="tree" aria-label="Span waterfall">
            {visible.map((r) => {
              const left = ((r.start - t0) / total) * 100;
              const width = Math.max(((r.end - r.start) / total) * 100, 0.35);
              const isError = r.span.status === "error" || !!r.span.error;
              const color = isError ? ERROR_COLOR : (KIND_COLOR[r.span.kind] ?? KIND_COLOR.internal);
              const isSel = r.span.id === selectedId;
              const isCollapsed = collapsed.has(r.span.id);
              return (
                <li
                  key={r.span.id}
                  role="treeitem"
                  aria-selected={isSel}
                  aria-expanded={r.hasChildren ? !isCollapsed : undefined}
                  tabIndex={0}
                  onClick={() => setSelectedId(isSel ? null : r.span.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedId(isSel ? null : r.span.id);
                    }
                  }}
                  className={cn(
                    "grid cursor-pointer grid-cols-[minmax(220px,34%)_1fr] items-center rounded-sm py-1 text-xs focus-visible:outline-none",
                    isSel ? "bg-accent-50 dark:bg-accent-500/10" : "hover:bg-zinc-50 focus-visible:bg-zinc-50 dark:hover:bg-zinc-900 dark:focus-visible:bg-zinc-900",
                  )}
                >
                  <div className="flex min-w-0 items-center gap-1 pr-3" style={{ paddingLeft: r.depth * 14 }}>
                    {r.hasChildren ? (
                      <button
                        type="button"
                        aria-label={isCollapsed ? "Expand" : "Collapse"}
                        onClick={(e) => {
                          e.stopPropagation();
                          setCollapsed((c) => {
                            const n = new Set(c);
                            if (n.has(r.span.id)) n.delete(r.span.id);
                            else n.add(r.span.id);
                            return n;
                          });
                        }}
                        className="rounded p-0.5 text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800"
                      >
                        <ChevronRight className={cn("size-3 transition-transform", !isCollapsed && "rotate-90")} />
                      </button>
                    ) : (
                      <span className="w-4 shrink-0" />
                    )}
                    <span className="size-2 shrink-0 rounded-sm" style={{ background: color }} />
                    <span className={cn("truncate font-mono", isError ? "text-rose-600 dark:text-rose-400" : "text-zinc-800 dark:text-zinc-200")}>
                      {r.span.name}
                    </span>
                    <span className="tabular ml-auto shrink-0 pl-2 font-mono text-[11px] text-zinc-500">
                      {fmtMs(r.span.duration_ms ?? (r.end - r.start) / 1000)}
                    </span>
                  </div>
                  <div className="relative h-5">
                    {ticks.slice(1, -1).map((t) => (
                      <span key={t} className="absolute inset-y-0 w-px bg-zinc-100 dark:bg-zinc-800/70" style={{ left: `${t * 100}%` }} />
                    ))}
                    <span
                      className="absolute top-1/2 h-3 -translate-y-1/2 rounded-[3px]"
                      style={{ left: `${Math.min(left, 99.65)}%`, width: `${width}%`, background: color }}
                      title={`${r.span.name}: ${fmtMs(r.span.duration_ms)}`}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
      {selected && (
        <div className="border-t border-zinc-200 p-4 dark:border-zinc-800">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-mono font-medium">{selected.name}</span>
            <Badge>{selected.kind}</Badge>
            <Badge tone={selected.status === "error" ? "danger" : "success"}>{selected.status}</Badge>
            <span className="tabular text-xs text-zinc-500">
              {fmtMs(selected.duration_ms)} / starts at +{fmtSpan((toMicros(selected.start_time) - t0) / 1000)}
            </span>
          </div>
          {selected.error && (
            <p className="mb-2 rounded-md bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
              {selected.error}
            </p>
          )}
          <JsonView value={selected.attributes} />
        </div>
      )}
    </div>
  );
}
