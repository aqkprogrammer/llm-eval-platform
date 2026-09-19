import { Link } from "react-router-dom";
import { ArrowRight, Boxes, Database, FileText, FlaskConical, Server, Waypoints } from "lucide-react";
import { useExperiments, useHealth, useMonitoring, useStats } from "../api/queries";
import type { MonitoringOverview } from "../api/types";
import { Sparkline } from "../components/charts/Sparkline";
import { GateBadge, StatusBadge } from "../components/StatusBadges";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Progress } from "../components/ui/Progress";
import { Skeleton, SkeletonRows } from "../components/ui/Skeleton";
import { StatCard } from "../components/ui/StatCard";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { fmtDate, fmtInt, fmtMs, fmtPct, fmtScore, fmtUsd, relativeTime } from "../lib/format";

function RecentExperiments() {
  const { data, isLoading, error, refetch } = useExperiments(5);
  return (
    <Card className="lg:col-span-2">
      <CardHeader
        title="Recent experiments"
        description="Latest evaluation runs across datasets"
        actions={
          <Link
            to="/experiments"
            className="inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:underline dark:text-accent-400"
          >
            View all <ArrowRight className="size-3" />
          </Link>
        }
      />
      {isLoading ? (
        <SkeletonRows rows={5} cols={4} />
      ) : error ? (
        <div className="p-4">
          <ErrorState error={error} onRetry={() => void refetch()} />
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={<FlaskConical className="size-5" />}
          title="No experiments yet"
          description="Run your first evaluation to compare prompts and models on a dataset."
          action={
            <Link to="/experiments?new=1" className="text-sm font-medium text-accent-600 hover:underline dark:text-accent-400">
              Create an experiment
            </Link>
          }
        />
      ) : (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800/70">
          {data.map((e) => {
            const active = e.status === "running" || e.status === "queued";
            return (
              <li key={e.id}>
                <Link
                  to={`/experiments/${e.id}`}
                  className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">{e.name}</div>
                    <div className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
                      {e.dataset_name ?? "unknown dataset"} / {e.variant_count} variants / {relativeTime(e.created_at)}
                    </div>
                    {active && (
                      <Progress className="mt-2 max-w-xs" value={e.progress_done} max={e.progress_total || 1} />
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StatusBadge status={e.status} />
                    {e.status === "completed" && <GateBadge passed={e.gate_passed} compact />}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function ProviderStatus() {
  const { data, isLoading, error } = useHealth();
  return (
    <Card>
      <CardHeader title="System status" description="Providers, judge and storage" />
      <div className="p-4">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-5" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} title="API unreachable" />
        ) : data ? (
          <div className="space-y-4 text-sm">
            <ul className="space-y-2">
              {Object.entries(data.providers).map(([name, ok]) => (
                <li key={name} className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300">
                    <Server className="size-3.5 text-zinc-400" />
                    {name}
                  </span>
                  <Badge tone={ok ? "success" : "neutral"} dot>
                    {ok ? "configured" : "not configured"}
                  </Badge>
                </li>
              ))}
            </ul>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-zinc-100 pt-3 text-xs dark:border-zinc-800">
              <dt className="text-zinc-500 dark:text-zinc-400">Judge</dt>
              <dd className="truncate text-right font-mono text-zinc-800 dark:text-zinc-200">
                {data.judge.provider}/{data.judge.model}
              </dd>
              <dt className="text-zinc-500 dark:text-zinc-400">Database</dt>
              <dd className="text-right text-zinc-800 dark:text-zinc-200">
                {data.database.dialect} {data.database.ok ? "(ok)" : "(down)"}
              </dd>
              <dt className="text-zinc-500 dark:text-zinc-400">OTel exporter</dt>
              <dd className="text-right text-zinc-800 dark:text-zinc-200">{data.tracing.otel_exporter}</dd>
              <dt className="text-zinc-500 dark:text-zinc-400">Langfuse</dt>
              <dd className="text-right text-zinc-800 dark:text-zinc-200">{data.tracing.langfuse ? "enabled" : "off"}</dd>
              <dt className="text-zinc-500 dark:text-zinc-400">Version</dt>
              <dd className="text-right font-mono text-zinc-800 dark:text-zinc-200">{data.version}</dd>
            </dl>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function MiniMetric({
  label,
  value,
  data,
  dataKey,
  color,
  fmt,
}: {
  label: string;
  value: string;
  data: MonitoringOverview["series"];
  dataKey: string;
  color: string;
  fmt: (v: number) => string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-zinc-100 p-3 dark:border-zinc-800/80">
      <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="tabular mt-0.5 text-lg font-semibold text-zinc-900 dark:text-zinc-50">{value}</div>
      <div className="mt-2">
        <Sparkline
          data={data as unknown as Record<string, unknown>[]}
          dataKey={dataKey}
          name={label}
          color={color}
          valueFormatter={fmt}
          labelFormatter={(l) => fmtDate(String(l))}
        />
      </div>
    </div>
  );
}

function MonitoringSnapshot() {
  const { data, isLoading, error } = useMonitoring("24h", 24);
  return (
    <Card className="lg:col-span-3">
      <CardHeader
        title="Production, last 24 hours"
        description="Traces reported via the SDK or the ingestion API, scored asynchronously"
        actions={
          <Link
            to="/monitoring"
            className="inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:underline dark:text-accent-400"
          >
            Open monitoring <ArrowRight className="size-3" />
          </Link>
        }
      />
      <div className="p-4">
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} />
        ) : data && data.totals.traces === 0 ? (
          <EmptyState
            icon={<Waypoints className="size-5" />}
            title="No production traces in this window"
            description="Instrument your app with the @observe decorator or POST /api/traces to start monitoring."
          />
        ) : data ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MiniMetric
              label="Trace volume"
              value={fmtInt(data.totals.traces)}
              data={data.series}
              dataKey="count"
              color="var(--chart-1)"
              fmt={(v) => fmtInt(v)}
            />
            <MiniMetric
              label="Latency p95"
              value={fmtMs(data.totals.latency_p95)}
              data={data.series}
              dataKey="latency_p95"
              color="var(--chart-2)"
              fmt={fmtMs}
            />
            <MiniMetric
              label="Answer relevancy (mean)"
              value={fmtScore(data.metrics.answer_relevancy?.mean)}
              data={data.series}
              dataKey="answer_relevancy"
              color="var(--chart-3)"
              fmt={(v) => fmtScore(v)}
            />
            <MiniMetric
              label="Cost"
              value={fmtUsd(data.totals.cost_usd)}
              data={data.series}
              dataKey="cost_usd"
              color="var(--chart-7)"
              fmt={fmtUsd}
            />
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-zinc-500 sm:col-span-2 lg:col-span-4 dark:text-zinc-400">
              <span>
                Error rate <span className="font-medium text-zinc-800 dark:text-zinc-200">{fmtPct(data.totals.error_rate)}</span>
              </span>
              <span>
                Flagged{" "}
                <span className={data.totals.flagged ? "font-medium text-rose-600 dark:text-rose-400" : "font-medium"}>
                  {fmtInt(data.totals.flagged)}
                </span>
              </span>
              <span>
                Pending scoring <span className="font-medium text-zinc-800 dark:text-zinc-200">{fmtInt(data.totals.pending_scoring)}</span>
              </span>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  useDocumentTitle("Overview");
  const { data: stats, isLoading, error } = useStats();
  return (
    <>
      <PageHeader
        title="Overview"
        description="Offline evaluation and production monitoring for your LLM applications."
        actions={
          <Link
            to="/experiments?new=1"
            className="inline-flex h-8.5 items-center gap-2 rounded-md bg-accent-600 px-3.5 text-sm font-medium text-white shadow-sm hover:bg-accent-500"
          >
            <FlaskConical className="size-4" /> New experiment
          </Link>
        }
      />
      {error && <ErrorState error={error} className="mb-4" />}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard
          label="Experiments"
          icon={<FlaskConical className="size-4" />}
          loading={isLoading}
          value={fmtInt(stats?.experiments)}
          sub={stats?.experiments_running ? `${stats.experiments_running} running` : "none running"}
        />
        <StatCard label="Datasets" icon={<Database className="size-4" />} loading={isLoading} value={fmtInt(stats?.datasets)} />
        <StatCard label="Prompt templates" icon={<FileText className="size-4" />} loading={isLoading} value={fmtInt(stats?.prompts)} />
        <StatCard label="Model configs" icon={<Boxes className="size-4" />} loading={isLoading} value={fmtInt(stats?.models)} />
        <StatCard
          label="Production traces"
          icon={<Waypoints className="size-4" />}
          loading={isLoading}
          value={fmtInt(stats?.traces_production)}
        />
        <StatCard
          label="All traces"
          icon={<Waypoints className="size-4" />}
          loading={isLoading}
          value={fmtInt(stats?.traces_total)}
          sub="incl. experiment runs"
        />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <RecentExperiments />
        <ProviderStatus />
        <MonitoringSnapshot />
      </div>
    </>
  );
}
