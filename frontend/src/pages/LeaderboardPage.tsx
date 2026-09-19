import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Trophy } from "lucide-react";
import { useDatasets, useLeaderboard } from "../api/queries";
import type { LeaderboardRow } from "../api/types";
import { ChartTooltip } from "../components/charts/ChartTooltip";
import { ScoreBar } from "../components/MetricChip";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Field, Select } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton, SkeletonRows } from "../components/ui/Skeleton";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMetricIndex } from "../hooks/useMetricIndex";
import { useQueryParams } from "../hooks/useSearchParam";
import { cursorFill, gridProps } from "../lib/chart";
import { fmtMetric, fmtMs, fmtPct, fmtScore, fmtUsd, relativeTime, truncate } from "../lib/format";
import { QUALITY_CATEGORIES, categoryRank } from "../lib/metrics";

function keyMetrics(rows: LeaderboardRow[], index: ReturnType<typeof useMetricIndex>): string[] {
  const counts = new Map<string, number>();
  for (const r of rows)
    for (const [k, v] of Object.entries(r.metrics)) {
      const info = index.get(k);
      if (v !== null && info && info.unit === "score" && QUALITY_CATEGORIES.has(info.category))
        counts.set(k, (counts.get(k) ?? 0) + 1);
    }
  return [...counts.entries()]
    .sort(
      (a, b) =>
        b[1] - a[1] ||
        categoryRank(index.get(a[0])?.category ?? "") - categoryRank(index.get(b[0])?.category ?? "") ||
        a[0].localeCompare(b[0]),
    )
    .slice(0, 4)
    .map(([k]) => k);
}

function CompositeChart({ rows, showDataset }: { rows: LeaderboardRow[]; showDataset: boolean }) {
  const data = rows
    .filter((r) => r.composite_score !== null)
    .slice(0, 15)
    .map((r, i) => ({
      name: `${showDataset ? `${r.dataset_name}: ` : ""}${r.model_config_name} / ${r.prompt} v${r.prompt_version}`,
      value: r.composite_score,
      i,
    }));
  const labelWidth = showDataset ? 290 : 230;
  const height = Math.max(160, data.length * 30 + 30);
  return (
    <Card>
      <CardHeader title="Composite score" description="Top variants, higher is better" />
      <div className="p-4" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 48, bottom: 0, left: 0 }} barCategoryGap={6}>
            <CartesianGrid {...gridProps} horizontal={false} vertical />
            <XAxis type="number" domain={[0, 1]} hide />
            <YAxis
              type="category"
              dataKey="name"
              width={labelWidth}
              tickLine={false}
              axisLine={false}
              tick={({ x, y, payload }) => (
                <text x={Number(x) - 6} y={Number(y)} dy={4} textAnchor="end" fill="var(--chart-axis)" fontSize={11}>
                  {truncate(String(payload?.value ?? ""), 44)}
                </text>
              )}
            />
            <Tooltip
              cursor={cursorFill}
              content={({ active, payload, label }) => (
                <ChartTooltip active={active} payload={payload} label={label} valueFormatter={(v) => fmtScore(v)} />
              )}
            />
            <Bar dataKey="value" name="Composite" radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={20}>
              {data.map((d) => (
                <Cell key={d.i} fill={d.i === 0 ? "var(--chart-7)" : "var(--chart-1)"} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                fill="var(--chart-axis)"
                fontSize={11}
                formatter={(v) => (typeof v === "number" ? v.toFixed(3) : "")}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export default function LeaderboardPage() {
  useDocumentTitle("Leaderboard");
  const q = useQueryParams<"dataset_id">();
  const datasetId = q.get("dataset_id");
  const datasets = useDatasets();
  const { data, isLoading, error, refetch } = useLeaderboard(datasetId || undefined);
  const index = useMetricIndex();
  const rows = useMemo(() => data?.rows ?? [], [data]);
  const metrics = useMemo(() => keyMetrics(rows, index), [rows, index]);

  return (
    <>
      <PageHeader
        title="Leaderboard"
        description="Latest result per dataset, prompt version and model across completed experiments."
        actions={
          <Field label="Dataset" htmlFor="lb-dataset" className="w-64">
            <Select
              id="lb-dataset"
              value={datasetId}
              onChange={(e) => q.set({ dataset_id: e.target.value })}
              placeholder="All datasets"
              options={(datasets.data ?? []).map((d) => ({ value: d.id, label: d.name }))}
            />
          </Field>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <div className="space-y-6">
          <Skeleton className="h-64" />
          <Card>
            <SkeletonRows rows={8} cols={7} />
          </Card>
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Trophy className="size-5" />}
            title="Nothing ranked yet"
            description="Complete an experiment to populate the leaderboard."
            action={
              <Link to="/experiments?new=1" className="text-sm font-medium text-accent-600 hover:underline dark:text-accent-400">
                Create an experiment
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="space-y-6">
          <CompositeChart rows={rows} showDataset={!datasetId} />
          <Card>
            <CardHeader title="Rankings" description={`${rows.length} entries`} />
            <Table>
              <THead>
                <tr>
                  <Th className="w-10">#</Th>
                  <Th>Model config</Th>
                  <Th>Prompt</Th>
                  {!datasetId && <Th>Dataset</Th>}
                  <Th>Composite</Th>
                  <Th className="text-right">Pass rate</Th>
                  {metrics.map((m) => (
                    <Th key={m} className="text-right font-mono normal-case">
                      {m}
                    </Th>
                  ))}
                  <Th className="text-right">Latency p95</Th>
                  <Th className="text-right">Cost</Th>
                  <Th>Experiment</Th>
                </tr>
              </THead>
              <TBody>
                {rows.map((r, i) => (
                  <Tr key={`${r.experiment_id}-${r.variant_id}`}>
                    <Td className="tabular text-zinc-500">{i + 1}</Td>
                    <Td className="whitespace-nowrap">
                      <div className="font-medium text-zinc-900 dark:text-zinc-100">{r.model_config_name}</div>
                      <div className="mt-0.5 flex items-center gap-1 text-xs text-zinc-500">
                        <Badge>{r.provider}</Badge>
                        <span className="font-mono">{r.model}</span>
                      </div>
                    </Td>
                    <Td className="whitespace-nowrap">
                      {r.prompt} <span className="font-mono text-xs text-zinc-500">v{r.prompt_version}</span>
                    </Td>
                    {!datasetId && <Td className="whitespace-nowrap text-zinc-600 dark:text-zinc-400">{r.dataset_name}</Td>}
                    <Td>
                      <ScoreBar value={r.composite_score} />
                    </Td>
                    <Td className="tabular text-right">{fmtPct(r.pass_rate)}</Td>
                    {metrics.map((m) => (
                      <Td key={m} className="tabular text-right font-mono text-xs">
                        {fmtMetric(r.metrics[m], index.get(m)?.unit)}
                      </Td>
                    ))}
                    <Td className="tabular text-right font-mono text-xs">{fmtMs(r.latency_p95)}</Td>
                    <Td className="tabular text-right font-mono text-xs">{fmtUsd(r.total_cost_usd)}</Td>
                    <Td className="max-w-48">
                      <Link
                        to={`/experiments/${r.experiment_id}`}
                        className="block truncate text-xs text-accent-600 hover:underline dark:text-accent-400"
                      >
                        {r.experiment_name}
                      </Link>
                      <span className="text-[11px] text-zinc-500">{relativeTime(r.finished_at)}</span>
                    </Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          </Card>
        </div>
      )}
    </>
  );
}
