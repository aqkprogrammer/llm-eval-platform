import { useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, AlertTriangle, Clock, DollarSign, Flag, Hourglass, Send, Waypoints } from "lucide-react";
import { useMonitoring } from "../api/queries";
import type { MonitoringOverview } from "../api/types";
import { ChartLegend, ChartTooltip } from "../components/charts/ChartTooltip";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader } from "../components/ui/Card";
import { CodeBlock } from "../components/ui/CodeBlock";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Field, Select } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { StatCard } from "../components/ui/StatCard";
import { Tabs } from "../components/ui/Tabs";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMetricIndex } from "../hooks/useMetricIndex";
import { useQueryParams } from "../hooks/useSearchParam";
import { cursorFill, cursorLine, gridProps, timeTick, xAxisProps, yAxisProps } from "../lib/chart";
import { cn } from "../lib/cn";
import { fmtDateTime, fmtInt, fmtMetric, fmtMs, fmtPct, fmtScore, fmtUsd, relativeTime } from "../lib/format";

const WINDOWS = {
  "1h": 12,
  "6h": 24,
  "24h": 24,
  "7d": 28,
} as const;
type WindowKey = keyof typeof WINDOWS;

const SAFETY_METRICS = ["toxicity", "prompt_injection", "pii_leakage"];
const QUALITY_METRICS = ["answer_relevancy", "faithfulness"];

function ChartCard({
  title,
  description,
  legend,
  children,
}: {
  title: string;
  description?: string;
  legend?: { label: string; color: string; dashed?: boolean }[];
  children: ReactElement;
}) {
  return (
    <Card>
      <CardHeader title={title} description={description} />
      <div className="space-y-3 p-4">
        {legend && <ChartLegend items={legend} />}
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            {children}
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}

function Charts({ data, window }: { data: MonitoringOverview; window: string }) {
  const series = data.series.map((b) => ({ ...b, ok: b.count - b.errors }));
  const tick = (v: string) => timeTick(v, window);
  const label = (l: unknown) => fmtDateTime(String(l));
  const presentSafety = SAFETY_METRICS.filter((m) => m in data.metrics);
  const presentQuality = QUALITY_METRICS.filter((m) => m in data.metrics);
  const qualityColors = ["var(--chart-3)", "var(--chart-7)"];
  const safetyColors = ["var(--chart-8)", "var(--chart-4)", "var(--chart-5)"];

  return (
    <div className="grid gap-6 xl:grid-cols-2 [&>*]:min-w-0">
      <ChartCard
        title="Volume and errors"
        description="Traces per bucket"
        legend={[
          { label: "ok", color: "var(--chart-1)" },
          { label: "errors", color: "var(--chart-bad)" },
        ]}
      >
        <BarChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="ts" {...xAxisProps} tickFormatter={tick} minTickGap={24} />
          <YAxis {...yAxisProps} allowDecimals={false} />
          <Tooltip
            cursor={cursorFill}
            content={({ active, payload, label: l }) => (
              <ChartTooltip active={active} payload={payload} label={l} labelFormatter={label} valueFormatter={(v) => fmtInt(v)} />
            )}
          />
          <Bar dataKey="ok" name="ok" stackId="v" fill="var(--chart-1)" isAnimationActive={false} />
          <Bar dataKey="errors" name="errors" stackId="v" fill="var(--chart-bad)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ChartCard>

      <ChartCard
        title="Latency"
        description="p50 and p95 per bucket"
        legend={[
          { label: "p50", color: "var(--chart-1)" },
          { label: "p95", color: "var(--chart-2)" },
        ]}
      >
        <LineChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: -4 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="ts" {...xAxisProps} tickFormatter={tick} minTickGap={24} />
          <YAxis {...yAxisProps} tickFormatter={(v: number) => `${Math.round(v)}`} width={48} />
          <Tooltip
            cursor={cursorLine}
            content={({ active, payload, label: l }) => (
              <ChartTooltip active={active} payload={payload} label={l} labelFormatter={label} valueFormatter={(v) => fmtMs(v)} />
            )}
          />
          <Line dataKey="latency_p50" name="p50" stroke="var(--chart-1)" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
          <Line dataKey="latency_p95" name="p95" stroke="var(--chart-2)" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        </LineChart>
      </ChartCard>

      <ChartCard
        title="Quality"
        description="Mean monitoring score per bucket, higher is better"
        legend={presentQuality.map((m, i) => ({ label: m, color: qualityColors[i] }))}
      >
        <LineChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="ts" {...xAxisProps} tickFormatter={tick} minTickGap={24} />
          <YAxis {...yAxisProps} domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} />
          <Tooltip
            cursor={cursorLine}
            content={({ active, payload, label: l }) => (
              <ChartTooltip active={active} payload={payload} label={l} labelFormatter={label} valueFormatter={(v) => fmtScore(v)} />
            )}
          />
          {presentQuality.map((m, i) => (
            <Line
              key={m}
              dataKey={m}
              name={m}
              stroke={qualityColors[i]}
              strokeWidth={2}
              dot={{ r: 2, strokeWidth: 0, fill: qualityColors[i] }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartCard>

      <ChartCard
        title="Safety signals"
        description="Mean safety score per bucket, lower is better (failures are counted in the table below)"
        legend={presentSafety.map((m, i) => ({ label: m, color: safetyColors[i] }))}
      >
        <LineChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="ts" {...xAxisProps} tickFormatter={tick} minTickGap={24} />
          <YAxis {...yAxisProps} domain={[0, (max: number) => Math.max(1, max)]} />
          <Tooltip
            cursor={cursorLine}
            content={({ active, payload, label: l }) => (
              <ChartTooltip active={active} payload={payload} label={l} labelFormatter={label} valueFormatter={(v) => fmtScore(v)} />
            )}
          />
          {presentSafety.map((m, i) => (
            <Line
              key={m}
              dataKey={m}
              name={m}
              stroke={safetyColors[i]}
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartCard>
    </div>
  );
}

function MetricTable({ data }: { data: MonitoringOverview }) {
  const index = useMetricIndex();
  const rows = Object.entries(data.metrics).sort((a, b) => b[1].failures - a[1].failures || a[0].localeCompare(b[0]));
  return (
    <Card>
      <CardHeader title="Metric totals" description="Across the whole window" />
      {rows.length === 0 ? (
        <EmptyState title="No scores yet" description="Scores appear once traces are evaluated." />
      ) : (
        <Table>
          <THead>
            <tr>
              <Th>Metric</Th>
              <Th className="text-right">Mean</Th>
              <Th className="text-right">Scored</Th>
              <Th className="text-right">Failures</Th>
              <Th className="text-right">Fail rate</Th>
            </tr>
          </THead>
          <TBody>
            {rows.map(([name, m]) => (
              <Tr key={name}>
                <Td className="font-mono text-xs">{name}</Td>
                <Td className="tabular text-right font-mono text-xs">{fmtMetric(m.mean, index.get(name)?.unit)}</Td>
                <Td className="tabular text-right">{fmtInt(m.n)}</Td>
                <Td className={cn("tabular text-right", m.failures > 0 && "font-medium text-rose-600 dark:text-rose-400")}>
                  {fmtInt(m.failures)}
                </Td>
                <Td className="tabular text-right text-zinc-500">{m.n ? fmtPct(m.failures / m.n) : "—"}</Td>
              </Tr>
            ))}
          </TBody>
        </Table>
      )}
    </Card>
  );
}

function FlaggedList({ data }: { data: MonitoringOverview }) {
  return (
    <Card>
      <CardHeader
        title="Flagged traces"
        description="Failed a safety or hallucination metric"
        actions={
          <Link to="/traces?source=production&flagged=1" className="text-xs font-medium text-accent-600 hover:underline dark:text-accent-400">
            View in traces
          </Link>
        }
      />
      {data.flagged.length === 0 ? (
        <EmptyState icon={<Flag className="size-5" />} title="Nothing flagged" description="No production trace failed a safety or faithfulness check in this window." />
      ) : (
        <ul className="max-h-96 divide-y divide-zinc-100 overflow-y-auto dark:divide-zinc-800/70">
          {data.flagged.map((f) => (
            <li key={f.id}>
              <Link to={`/traces/${f.id}`} className="block px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900/60">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm text-zinc-800 dark:text-zinc-200">{f.input_preview}</span>
                  <span className="shrink-0 text-xs text-zinc-500" title={fmtDateTime(f.start_time)}>
                    {relativeTime(f.start_time)}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-zinc-500">
                  <span className="font-mono">{f.model}</span>
                  {f.failed_metrics.map((m) => (
                    <Badge key={m} tone="danger">
                      {m}
                    </Badge>
                  ))}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const CURL = `curl -X POST http://localhost:8000/api/traces \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "support-chat",
    "input": "How long do I have to return an item?",
    "output": "You can return items within 30 days of delivery.",
    "context": ["Acme accepts returns within 30 days of delivery."],
    "provider": "anthropic",
    "model": "claude-sonnet-5",
    "latency_ms": 812,
    "input_tokens": 64,
    "output_tokens": 18
  }'`;

const PYTHON = `from evalplatform.sdk import observe, configure
configure(base_url="http://localhost:8000")
@observe(name="support-chat", model="claude-sonnet-5", provider="anthropic")
def answer(question: str) -> str: ...`;

function SendTraceCard() {
  const [tab, setTab] = useState<"curl" | "python">("curl");
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Send className="size-4 text-accent-500" /> Send a test trace
          </span>
        }
        description="Production traces are scored asynchronously with the monitoring metrics"
        actions={
          <Tabs
            ariaLabel="Snippet language"
            value={tab}
            onChange={setTab}
            items={[
              { value: "curl", label: "curl" },
              { value: "python", label: "Python SDK" },
            ]}
          />
        }
      />
      <div className="p-4">
        <CodeBlock>{tab === "curl" ? CURL : PYTHON}</CodeBlock>
      </div>
    </Card>
  );
}

export default function MonitoringPage() {
  useDocumentTitle("Monitoring");
  const q = useQueryParams<"window" | "model">();
  const windowKey = (q.get("window") in WINDOWS ? q.get("window") : "24h") as WindowKey;
  const buckets = WINDOWS[windowKey];
  const model = q.get("model");
  const all = useMonitoring(windowKey, buckets);
  const filtered = useMonitoring(windowKey, buckets, model || undefined);
  const { data, isLoading, error, refetch, isFetching } = model ? filtered : all;
  const modelOptions = Object.entries(all.data?.models ?? {}).map(([m, n]) => ({ value: m, label: `${m} (${n})` }));

  return (
    <>
      <PageHeader
        title="Monitoring"
        description="Quality, safety, latency and cost of production traffic."
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Model" htmlFor="mon-model" className="w-56">
              <Select
                id="mon-model"
                value={model}
                onChange={(e) => q.set({ model: e.target.value })}
                placeholder="All models"
                options={modelOptions}
              />
            </Field>
            <Tabs
              ariaLabel="Time window"
              value={windowKey}
              onChange={(v) => q.set({ window: v === "24h" ? null : v })}
              items={(Object.keys(WINDOWS) as WindowKey[]).map((w) => ({ value: w, label: w }))}
            />
          </div>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : isLoading || !data ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            {Array.from({ length: 7 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <div className="grid gap-6 xl:grid-cols-2 [&>*]:min-w-0">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-72" />
            ))}
          </div>
        </div>
      ) : (
        <div className={cn("space-y-6 transition-opacity", isFetching && "opacity-80")}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <StatCard label="Traces" icon={<Waypoints className="size-4" />} value={fmtInt(data.totals.traces)} />
            <StatCard
              label="Error rate"
              icon={<AlertTriangle className="size-4" />}
              value={fmtPct(data.totals.error_rate)}
              sub={`${fmtInt(data.totals.errors)} errors`}
              tone={data.totals.error_rate > 0.05 ? "danger" : undefined}
            />
            <StatCard label="Latency p50" icon={<Clock className="size-4" />} value={fmtMs(data.totals.latency_p50)} />
            <StatCard label="Latency p95" icon={<Clock className="size-4" />} value={fmtMs(data.totals.latency_p95)} />
            <StatCard label="Cost" icon={<DollarSign className="size-4" />} value={fmtUsd(data.totals.cost_usd)} />
            <StatCard
              label="Flagged"
              icon={<Flag className="size-4" />}
              value={fmtInt(data.totals.flagged)}
              tone={data.totals.flagged > 0 ? "danger" : undefined}
            />
            <StatCard
              label="Pending scoring"
              icon={<Hourglass className="size-4" />}
              value={fmtInt(data.totals.pending_scoring)}
              tone={data.totals.pending_scoring > 0 ? "warning" : undefined}
            />
          </div>
          {data.totals.traces === 0 ? (
            <Card>
              <EmptyState
                icon={<Activity className="size-5" />}
                title="No production traces in this window"
                description="Widen the window or send a trace using the snippet below."
              />
            </Card>
          ) : (
            <Charts data={data} window={windowKey} />
          )}
          <div className="grid items-start gap-6 xl:grid-cols-2 [&>*]:min-w-0">
            <MetricTable data={data} />
            <FlaggedList data={data} />
          </div>
          <SendTraceCard />
        </div>
      )}
    </>
  );
}
