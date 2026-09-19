import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { ChevronRight, CircleStop, Crown, GitCompareArrows, ListFilter } from "lucide-react";
import { ACTIVE_STATUSES, useCancelExperiment, useExperiment, useResults } from "../api/queries";
import type { CaseResult, Experiment, VariantSummary } from "../api/types";
import { ChartLegend, ChartTooltip } from "../components/charts/ChartTooltip";
import { ResultDrawer } from "../components/experiments/ResultDrawer";
import { MetricChip, ScoreBar } from "../components/MetricChip";
import { GateBadge, PassBadge, StatusBadge } from "../components/StatusBadges";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState, InlineError } from "../components/ui/ErrorState";
import { Select } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { Pagination } from "../components/ui/Pagination";
import { Progress } from "../components/ui/Progress";
import { Skeleton, SkeletonRows } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMetricIndex } from "../hooks/useMetricIndex";
import { cursorFill, gridProps, xAxisProps, yAxisProps } from "../lib/chart";
import { cn } from "../lib/cn";
import { fmtDateTime, fmtDuration, fmtInt, fmtMetric, fmtMs, fmtPct, fmtScore, fmtUsd, truncate } from "../lib/format";
import { QUALITY_CATEGORIES, categoryRank, seriesColor } from "../lib/metrics";

const PAGE_SIZE = 25;

function qualityMetricNames(variants: VariantSummary[]): string[] {
  const set = new Map<string, string>();
  for (const v of variants) {
    for (const [name, m] of Object.entries(v.metrics)) {
      if (m.unit === "score" && m.higher_is_better && QUALITY_CATEGORIES.has(m.category) && m.mean !== null) set.set(name, m.category);
    }
  }
  return [...set.entries()]
    .sort((a, b) => categoryRank(a[1]) - categoryRank(b[1]) || a[0].localeCompare(b[0]))
    .map(([n]) => n);
}

function Header({ exp }: { exp: Experiment }) {
  const cancel = useCancelExperiment();
  const active = ACTIVE_STATUSES.has(exp.status);
  const pct = exp.progress_total ? exp.progress_done / exp.progress_total : 0;
  return (
    <>
      <PageHeader
        breadcrumb={
          <span className="flex items-center gap-1">
            <Link to="/experiments" className="hover:text-zinc-900 dark:hover:text-zinc-100">
              Experiments
            </Link>
            <ChevronRight className="size-3" />
            <span className="truncate">{exp.name}</span>
          </span>
        }
        title={
          <span className="flex flex-wrap items-center gap-2.5">
            {exp.name}
            <StatusBadge status={exp.status} />
            {exp.status === "completed" && <GateBadge passed={exp.gate_passed} />}
          </span>
        }
        description={
          <span className="flex flex-wrap gap-x-4 gap-y-1">
            <span>
              Dataset{" "}
              <Link to={`/datasets/${exp.dataset_id}`} className="font-medium text-zinc-700 hover:underline dark:text-zinc-300">
                {exp.dataset_name ?? exp.dataset_id}
              </Link>
            </span>
            <span>{exp.variants.length} variants</span>
            <span>concurrency {exp.concurrency}</span>
            <span>started {fmtDateTime(exp.started_at ?? exp.created_at)}</span>
            {exp.finished_at && <span>took {fmtDuration(exp.started_at, exp.finished_at)}</span>}
          </span>
        }
        actions={
          <>
            {active && (
              <Button
                variant="danger"
                icon={<CircleStop className="size-4" />}
                loading={cancel.isPending}
                onClick={() => cancel.mutate(exp.id)}
              >
                Cancel
              </Button>
            )}
            <Link
              to={`/compare?baseline=${exp.id}`}
              className="inline-flex h-8.5 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3.5 text-sm font-medium text-zinc-800 shadow-xs hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              <GitCompareArrows className="size-4" /> Compare with...
            </Link>
          </>
        }
      />
      {cancel.error && <InlineError error={cancel.error} />}
      {exp.error &&
        (exp.status === "cancelled" ? (
          <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
            {exp.error}. Partial results are shown below.
          </p>
        ) : (
          <ErrorState className="mb-4" title="Experiment error" error={exp.error} />
        ))}
      {(active || exp.progress_total > exp.progress_done) && (
        <Card className="mb-6 p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">
              {exp.status === "queued" ? "Queued" : active ? "Running" : "Stopped"}: {fmtInt(exp.progress_done)} of{" "}
              {fmtInt(exp.progress_total)} runs
            </span>
            <span className="tabular text-zinc-500">
              {fmtPct(pct, 0)}
              {exp.progress_failed > 0 && <span className="ml-2 text-rose-600 dark:text-rose-400">{exp.progress_failed} failed</span>}
            </span>
          </div>
          <Progress value={exp.progress_done} max={exp.progress_total || 1} label="Experiment progress" />
        </Card>
      )}
    </>
  );
}

function LeaderboardTable({ variants, keyMetrics }: { variants: VariantSummary[]; keyMetrics: string[] }) {
  const index = useMetricIndex();
  return (
    <Card>
      <CardHeader title="Variant leaderboard" description="Ranked by composite score (mean of normalised quality metrics)" />
      <Table>
        <THead>
          <tr>
            <Th className="w-10">#</Th>
            <Th>Variant</Th>
            <Th>Composite</Th>
            <Th className="text-right">Pass rate</Th>
            {keyMetrics.map((m) => (
              <Th key={m} className="text-right font-mono normal-case">
                {m}
              </Th>
            ))}
            <Th className="text-right">Latency p95</Th>
            <Th className="text-right">Cost</Th>
            <Th>Gates</Th>
          </tr>
        </THead>
        <TBody>
          {variants.map((v) => {
            const failing = v.gates.filter((g) => !g.passed);
            return (
              <Tr key={v.variant_id}>
                <Td className="tabular">
                  {v.rank === 1 ? <Crown className="size-4 text-amber-500" aria-label="Rank 1" /> : v.rank}
                </Td>
                <Td className="min-w-44" title={v.label}>
                  <div className="font-medium whitespace-nowrap text-zinc-900 dark:text-zinc-100">
                    {v.prompt} <span className="font-mono text-xs text-zinc-500">v{v.prompt_version}</span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1 text-xs whitespace-nowrap text-zinc-500">
                    <Badge>{v.provider}</Badge>
                    <span className="font-mono">{v.model_config_name}</span>
                    {v.errors > 0 && <Badge tone="danger">{v.errors} errors</Badge>}
                  </div>
                </Td>
                <Td>
                  <ScoreBar value={v.composite_score} />
                </Td>
                <Td className="tabular text-right">{fmtPct(v.pass_rate)}</Td>
                {keyMetrics.map((m) => (
                  <Td key={m} className="tabular text-right font-mono text-xs">
                    {fmtMetric(v.metrics[m]?.mean, index.get(m)?.unit ?? v.metrics[m]?.unit)}
                  </Td>
                ))}
                <Td className="tabular text-right font-mono text-xs">{fmtMs(v.metrics.latency_ms?.p95)}</Td>
                <Td className="tabular text-right font-mono text-xs">{fmtUsd(v.total_cost_usd)}</Td>
                <Td>
                  {v.gates.length === 0 ? (
                    <GateBadge passed={null} compact />
                  ) : (
                    <div className="space-y-1">
                      <GateBadge passed={v.gate_passed} compact />
                      {failing.map((g) => (
                        <div key={g.metric} className="text-[11px] whitespace-nowrap text-rose-600 dark:text-rose-400">
                          {g.metric} {fmtMetric(g.actual, v.metrics[g.metric]?.unit)}{" "}
                          {g.min !== undefined ? `< ${g.min}` : g.max !== undefined ? `> ${g.max}` : ""}
                        </div>
                      ))}
                    </div>
                  )}
                </Td>
              </Tr>
            );
          })}
        </TBody>
      </Table>
    </Card>
  );
}

function QualityChart({ variants, metrics }: { variants: VariantSummary[]; metrics: string[] }) {
  const data = metrics.map((m) => {
    const row: Record<string, string | number | null> = { metric: m };
    variants.forEach((v, i) => {
      row[`v${i}`] = v.metrics[m]?.mean ?? null;
    });
    return row;
  });
  return (
    <Card>
      <CardHeader title="Quality metrics by variant" description="Mean score per metric (0 to 1)" />
      <div className="space-y-3 p-4">
        <ChartLegend items={variants.map((v, i) => ({ label: v.label, color: seriesColor(i) }))} />
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }} barGap={2} barCategoryGap="22%">
              <CartesianGrid {...gridProps} />
              <XAxis
                dataKey="metric"
                {...xAxisProps}
                interval={0}
                angle={-20}
                textAnchor="end"
                height={56}
                tick={{ ...xAxisProps.tick, fontSize: 10 }}
                tickFormatter={(v: string) => v.replace(/_/g, " ")}
              />
              <YAxis {...yAxisProps} domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} />
              <Tooltip
                cursor={cursorFill}
                content={({ active, payload, label }) => (
                  <ChartTooltip active={active} payload={payload} label={label} valueFormatter={(v) => fmtScore(v)} />
                )}
              />
              {variants.map((v, i) => (
                <Bar
                  key={v.variant_id}
                  dataKey={`v${i}`}
                  name={v.label}
                  fill={seriesColor(i)}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={22}
                  stroke="var(--surface)"
                  strokeWidth={1}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}

function TradeoffChart({ variants }: { variants: VariantSummary[] }) {
  const points = variants.map((v, i) => ({
    idx: i,
    rank: v.rank,
    label: v.label,
    latency: v.metrics.latency_ms?.mean ?? null,
    composite: v.composite_score,
    cost: v.total_cost_usd,
  }));
  return (
    <Card>
      <CardHeader title="Quality vs latency" description="Mean latency (x) against composite score (y); labels show rank" />
      <div className="space-y-3 p-4">
        <ChartLegend items={variants.map((v, i) => ({ label: `#${v.rank} ${v.label}`, color: seriesColor(i) }))} />
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 16, right: 16, bottom: 8, left: -8 }}>
              <CartesianGrid {...gridProps} vertical />
              <XAxis
                type="number"
                dataKey="latency"
                name="Latency"
                {...xAxisProps}
                tickFormatter={(v: number) => `${Math.round(v)}`}
                unit=" ms"
                domain={["auto", "auto"]}
              />
              <YAxis
                type="number"
                dataKey="composite"
                name="Composite"
                {...yAxisProps}
                domain={[(min: number) => Math.max(0, Math.floor((min - 0.05) * 10) / 10), 1]}
                tickFormatter={(v: number) => v.toFixed(2)}
              />
              <ZAxis range={[120, 120]} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3", stroke: "var(--chart-axis)" }}
                content={({ active, payload }) => {
                  const p = payload?.[0]?.payload as (typeof points)[number] | undefined;
                  if (!active || !p) return null;
                  return (
                    <ChartTooltip
                      active
                      label={p.label}
                      payload={[
                        { name: "Composite", value: p.composite ?? undefined, color: seriesColor(p.idx) },
                        { name: "Latency (mean)", value: fmtMs(p.latency), color: seriesColor(p.idx) },
                        { name: "Total cost", value: fmtUsd(p.cost), color: seriesColor(p.idx) },
                      ]}
                      valueFormatter={(v) => fmtScore(v)}
                    />
                  );
                }}
              />
              {points.map((p) => (
                <Scatter
                  key={p.idx}
                  data={[p]}
                  name={p.label}
                  fill={seriesColor(p.idx)}
                  stroke="var(--surface)"
                  strokeWidth={2}
                  isAnimationActive={false}
                >
                  <LabelList dataKey="rank" position="top" offset={10} fill="var(--chart-axis)" fontSize={11} formatter={(v) => `#${String(v)}`} />
                </Scatter>
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}

function ResultsSection({ exp, live }: { exp: Experiment; live: boolean }) {
  const [variantId, setVariantId] = useState("");
  const [passFilter, setPassFilter] = useState<"all" | "pass" | "fail">("all");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CaseResult | null>(null);
  const index = useMetricIndex();
  const filter = {
    variant_id: variantId || undefined,
    passed: passFilter === "all" ? undefined : passFilter === "pass",
    limit: PAGE_SIZE,
    offset,
  };
  const { data, isLoading, isFetching, error, refetch } = useResults(exp.id, filter, live);
  const labels = useMemo(() => new Map(exp.variants.map((v) => [v.id, v.label])), [exp.variants]);
  const chipMetrics = useMemo(() => {
    const names = exp.metrics.map((m) => m.name).filter((n) => index.get(n)?.unit === "score");
    return names.slice(0, 4);
  }, [exp.metrics, index]);

  return (
    <Card>
      <CardHeader
        title="Results"
        description="Every test case x variant with its scores. Click a row to inspect."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ListFilter className="size-4 text-zinc-400" aria-hidden />
            <Select
              aria-label="Filter by variant"
              className="w-60"
              value={variantId}
              onChange={(e) => {
                setVariantId(e.target.value);
                setOffset(0);
              }}
              placeholder="All variants"
              options={exp.variants.map((v) => ({ value: v.id, label: v.label }))}
            />
            <Tabs
              ariaLabel="Filter by result"
              value={passFilter}
              onChange={(v) => {
                setPassFilter(v);
                setOffset(0);
              }}
              items={[
                { value: "all", label: "All" },
                { value: "pass", label: "Passed" },
                { value: "fail", label: "Failed" },
              ]}
            />
          </div>
        }
      />
      {isLoading ? (
        <SkeletonRows rows={8} cols={5} />
      ) : error ? (
        <div className="p-4">
          <ErrorState error={error} onRetry={() => void refetch()} />
        </div>
      ) : !data?.items.length ? (
        <EmptyState
          title={live ? "Waiting for results" : "No results match"}
          description={live ? "Results appear here as cases finish." : "Try a different variant or pass filter."}
        />
      ) : (
        <div className={cn("transition-opacity", isFetching && !live && "opacity-70")}>
          <Table className="table-fixed">
            <THead>
              <tr>
                <Th className="w-[24%]">Input</Th>
                <Th className="w-[28%]">Output</Th>
                <Th className="w-[16%]">Variant</Th>
                <Th className="w-20">Result</Th>
                <Th>Scores</Th>
              </tr>
            </THead>
            <TBody>
              {data.items.map((r) => (
                <Tr
                  key={r.id}
                  interactive
                  tabIndex={0}
                  onClick={() => setSelected(r)}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(r)}
                >
                  <Td className="align-top">
                    <p className="line-clamp-2 text-zinc-800 dark:text-zinc-200">{r.input}</p>
                  </Td>
                  <Td className="align-top">
                    {r.error ? (
                      <p className="line-clamp-2 text-rose-600 dark:text-rose-400">{truncate(r.error, 160)}</p>
                    ) : (
                      <p className="line-clamp-2 text-zinc-600 dark:text-zinc-400">{r.output}</p>
                    )}
                  </Td>
                  <Td className="align-top text-xs text-zinc-500 dark:text-zinc-400">
                    <span className="line-clamp-2">{labels.get(r.variant_id) ?? r.variant_id}</span>
                  </Td>
                  <Td className="align-top">
                    <PassBadge passed={r.passed} />
                  </Td>
                  <Td className="align-top">
                    <div className="flex flex-wrap gap-1">
                      {chipMetrics.map((m) => {
                        const s = r.scores.find((x) => x.metric === m);
                        return s ? <MetricChip key={m} name={m} value={s.value} passed={s.passed} unit="score" /> : null;
                      })}
                      {r.scores.filter((s) => s.passed === false && !chipMetrics.includes(s.metric)).length > 0 && (
                        <Badge tone="danger">
                          +{r.scores.filter((s) => s.passed === false && !chipMetrics.includes(s.metric)).length} failing
                        </Badge>
                      )}
                    </div>
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </div>
      )}
      <ResultDrawer
        result={selected}
        variantLabel={selected ? labels.get(selected.variant_id) : undefined}
        onClose={() => setSelected(null)}
      />
    </Card>
  );
}

export default function ExperimentDetailPage() {
  const { id } = useParams();
  const { data: exp, isLoading, error, refetch } = useExperiment(id);
  useDocumentTitle(exp?.name ?? "Experiment");

  const variants = useMemo(
    () => [...(exp?.summary.variants ?? [])].sort((a, b) => a.rank - b.rank),
    [exp?.summary.variants],
  );
  const quality = useMemo(() => qualityMetricNames(variants), [variants]);
  const keyMetrics = useMemo(() => {
    const gated = (variants[0]?.gates ?? []).map((g) => g.metric).filter((m) => quality.includes(m));
    return [...new Set([...gated, ...quality])].slice(0, 4);
  }, [variants, quality]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-4 w-72" />
        <Skeleton className="h-48" />
        <Skeleton className="h-72" />
      </div>
    );
  }
  if (error || !exp) return <ErrorState error={error ?? "Experiment not found"} onRetry={() => void refetch()} />;

  const live = ACTIVE_STATUSES.has(exp.status);
  return (
    <div className="space-y-6">
      <Header exp={exp} />
      {variants.length > 0 ? (
        <>
          <LeaderboardTable variants={variants} keyMetrics={keyMetrics} />
          <div className="grid gap-6 xl:grid-cols-2 [&>*]:min-w-0">
            {quality.length > 0 && <QualityChart variants={variants} metrics={quality} />}
            <TradeoffChart variants={variants} />
          </div>
        </>
      ) : (
        <Card>
          <EmptyState
            title={live ? "Summary pending" : "No summary available"}
            description={
              live
                ? "The leaderboard and charts are computed when every case has been scored."
                : "This experiment finished without producing a summary."
            }
          />
        </Card>
      )}
      <ResultsSection exp={exp} live={live} />
    </div>
  );
}
