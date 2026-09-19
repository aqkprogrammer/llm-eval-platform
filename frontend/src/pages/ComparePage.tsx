import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowLeftRight, ArrowRight, CheckCircle2, GitCompareArrows } from "lucide-react";
import { useComparison, useExperiment, useExperiments } from "../api/queries";
import type { CaseDiffStatus, CompareCase, CompareMetric, Comparison, DeltaStatus } from "../api/types";
import { PassBadge } from "../components/StatusBadges";
import { Badge, type Tone } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Field, Select } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton, SkeletonRows } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMetricIndex } from "../hooks/useMetricIndex";
import { useQueryParams } from "../hooks/useSearchParam";
import { cn } from "../lib/cn";
import { fmtDelta, fmtInt, fmtMetric, fmtPct, fmtScore } from "../lib/format";
import { deltaTone } from "../lib/metrics";

type Key = "baseline" | "candidate" | "baseline_variant" | "candidate_variant" | "tolerance";

const STATUS_TONE: Record<DeltaStatus | CaseDiffStatus, Tone> = {
  improved: "success",
  regressed: "danger",
  unchanged: "neutral",
  missing: "warning",
  mixed: "warning",
};

function Picker({
  label,
  expId,
  variantId,
  onExp,
  onVariant,
}: {
  label: string;
  expId: string;
  variantId: string;
  onExp: (id: string) => void;
  onVariant: (id: string) => void;
}) {
  const exps = useExperiments(200);
  const exp = useExperiment(expId || undefined);
  const slug = label.toLowerCase();
  return (
    <div className="grid flex-1 gap-3 sm:grid-cols-2">
      <Field label={`${label} experiment`} htmlFor={`${slug}-exp`}>
        <Select
          id={`${slug}-exp`}
          value={expId}
          onChange={(e) => onExp(e.target.value)}
          placeholder={exps.isLoading ? "Loading..." : "Select an experiment"}
          options={(exps.data ?? [])
            .filter((e) => e.status === "completed" || e.id === expId)
            .map((e) => ({ value: e.id, label: `${e.name} (${e.dataset_name ?? "?"})` }))}
        />
      </Field>
      <Field label={`${label} variant`} htmlFor={`${slug}-var`}>
        <Select
          id={`${slug}-var`}
          value={variantId}
          disabled={!expId}
          onChange={(e) => onVariant(e.target.value)}
          placeholder="All variants (pooled)"
          options={(exp.data?.variants ?? []).map((v) => ({ value: v.id, label: v.label }))}
        />
      </Field>
    </div>
  );
}

function DeltaCell({ m }: { m: CompareMetric }) {
  const tone = deltaTone(m.delta, m.higher_is_better);
  return (
    <span
      className={cn(
        "tabular font-mono text-xs",
        tone === "good" && "text-emerald-600 dark:text-emerald-400",
        tone === "bad" && "text-rose-600 dark:text-rose-400",
        tone === "neutral" && "text-zinc-500",
      )}
    >
      {fmtDelta(m.delta, m.unit)}
    </span>
  );
}

function Summary({ c }: { c: Comparison }) {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
      {[c.baseline, null, c.candidate].map((side, i) =>
        side === null ? (
          <div key="arrow" className="hidden items-center justify-center md:flex">
            <ArrowRight className="size-5 text-zinc-400" />
          </div>
        ) : (
          <Card key={i} className="p-4">
            <div className="text-xs font-medium tracking-wide text-zinc-500 uppercase">{i === 0 ? "Baseline" : "Candidate"}</div>
            <Link
              to={`/experiments/${side.experiment_id}`}
              className="mt-1 block truncate font-medium text-zinc-900 hover:underline dark:text-zinc-100"
              title={side.label}
            >
              {side.label}
            </Link>
            <div className="mt-3 flex items-end justify-between">
              <div>
                <div className="text-xs text-zinc-500">Composite</div>
                <div className="tabular text-2xl font-semibold">{fmtScore(side.composite_score)}</div>
              </div>
              <div className="text-right text-xs text-zinc-500">{fmtInt(side.cases)} case results</div>
            </div>
          </Card>
        ),
      )}
    </div>
  );
}

function CaseDiff({ c, units }: { c: CompareCase; units: Map<string, { unit: string; hib: boolean }> }) {
  const metrics = Object.keys(c.deltas).sort();
  return (
    <div className="space-y-3 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm font-medium text-zinc-900 dark:text-zinc-100">{c.input}</p>
        <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge>
      </div>
      {c.expected_output && (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          <span className="font-medium">Expected:</span> {c.expected_output}
        </p>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {(
          [
            ["Baseline", c.baseline_output, c.baseline_passed],
            ["Candidate", c.candidate_output, c.candidate_passed],
          ] as const
        ).map(([label, out, passed]) => (
          <div key={label} className="rounded-md border border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center justify-between border-b border-zinc-200 px-3 py-1.5 text-xs dark:border-zinc-800">
              <span className="font-medium text-zinc-600 dark:text-zinc-400">{label}</span>
              <PassBadge passed={passed} />
            </div>
            <p className="px-3 py-2 text-sm whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
              {out ?? <span className="text-zinc-400 italic">no output</span>}
            </p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {metrics.map((m) => {
          const d = c.deltas[m];
          const info = units.get(m);
          const regressed = c.regressed_metrics.includes(m);
          const improved = c.improved_metrics.includes(m);
          return (
            <span
              key={m}
              title={`${m}: ${fmtMetric(c.baseline_metrics[m], info?.unit)} -> ${fmtMetric(c.candidate_metrics[m], info?.unit)}`}
              className={cn(
                "tabular inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-inset",
                regressed && "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:ring-rose-500/20",
                improved &&
                  "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/20",
                !regressed && !improved && "bg-zinc-50 text-zinc-500 ring-zinc-200 dark:bg-zinc-800/50 dark:ring-zinc-700/50",
              )}
            >
              <span className="font-sans text-[10px] opacity-75">{m}</span>
              {fmtDelta(d, info?.unit)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Results({ c }: { c: Comparison }) {
  const [filter, setFilter] = useState<"all" | CaseDiffStatus>("all");
  const [limit, setLimit] = useState(20);
  const index = useMetricIndex();
  const units = useMemo(() => {
    const m = new Map<string, { unit: string; hib: boolean }>();
    for (const x of c.metrics) m.set(x.metric, { unit: x.unit, hib: x.higher_is_better });
    for (const [k, v] of index) if (!m.has(k)) m.set(k, { unit: v.unit, hib: v.higher_is_better });
    return m;
  }, [c.metrics, index]);
  const cases = c.cases.filter((x) => filter === "all" || x.status === filter);

  return (
    <div className="space-y-6">
      <Summary c={c} />
      {c.has_regression ? (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm dark:border-rose-900/50 dark:bg-rose-950/30"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rose-500" />
          <div>
            <p className="font-medium text-rose-800 dark:text-rose-300">Regression detected</p>
            <p className="mt-0.5 text-rose-700/90 dark:text-rose-300/80">
              The candidate is worse than the baseline beyond the tolerance ({c.tolerance}) on:{" "}
              {c.regressions.map((r) => (
                <code key={r} className="mx-0.5 rounded bg-rose-100 px-1 font-mono text-xs dark:bg-rose-900/40">
                  {r}
                </code>
              ))}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300">
          <CheckCircle2 className="size-4 shrink-0" /> No regressions beyond the tolerance of {c.tolerance}.
        </div>
      )}
      {!c.same_dataset && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          These experiments use different datasets, so only aggregate metrics are compared (no per-case diff).
        </p>
      )}

      <Card>
        <CardHeader title="Metrics" description="Mean per metric; delta colour follows each metric's direction" />
        <Table>
          <THead>
            <tr>
              <Th>Metric</Th>
              <Th className="text-right">Baseline</Th>
              <Th className="text-right">Candidate</Th>
              <Th className="text-right">Delta</Th>
              <Th className="text-right">Pass rate</Th>
              <Th>Status</Th>
            </tr>
          </THead>
          <TBody>
            {c.metrics.map((m) => (
              <Tr key={m.metric}>
                <Td>
                  <span className="font-mono text-xs font-medium">{m.metric}</span>
                  <span className="ml-2 text-[11px] text-zinc-400">{m.higher_is_better ? "higher is better" : "lower is better"}</span>
                </Td>
                <Td className="tabular text-right font-mono text-xs">{fmtMetric(m.baseline, m.unit)}</Td>
                <Td className="tabular text-right font-mono text-xs">{fmtMetric(m.candidate, m.unit)}</Td>
                <Td className="text-right">
                  <DeltaCell m={m} />
                </Td>
                <Td className="tabular text-right text-xs text-zinc-500">
                  {fmtPct(m.baseline_pass_rate)} {"->"} {fmtPct(m.candidate_pass_rate)}
                </Td>
                <Td>
                  <Badge tone={STATUS_TONE[m.status]}>{m.status}</Badge>
                </Td>
              </Tr>
            ))}
          </TBody>
        </Table>
      </Card>

      {c.same_dataset && (
        <Card>
          <CardHeader
            title="Per-case diff"
            description="Outputs side by side with per-metric deltas (candidate minus baseline)"
            actions={
              <Tabs
                ariaLabel="Filter cases"
                value={filter}
                onChange={(v) => {
                  setFilter(v);
                  setLimit(20);
                }}
                items={[
                  { value: "all", label: "All", count: c.cases.length },
                  { value: "regressed", label: "Regressed", count: c.case_summary.regressed },
                  { value: "improved", label: "Improved", count: c.case_summary.improved },
                  { value: "mixed", label: "Mixed", count: c.case_summary.mixed },
                  { value: "unchanged", label: "Unchanged", count: c.case_summary.unchanged },
                ]}
              />
            }
          />
          {cases.length === 0 ? (
            <EmptyState title="No cases in this bucket" description="Pick another filter to see more cases." />
          ) : (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800/70">
              {cases.slice(0, limit).map((x) => (
                <CaseDiff key={x.test_case_id} c={x} units={units} />
              ))}
              {cases.length > limit && (
                <div className="p-3 text-center">
                  <Button size="sm" onClick={() => setLimit((l) => l + 20)}>
                    Show more ({cases.length - limit} remaining)
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

export default function ComparePage() {
  useDocumentTitle("Compare");
  const q = useQueryParams<Key>();
  const baseline = q.get("baseline");
  const candidate = q.get("candidate");
  const tolerance = q.get("tolerance");
  const params =
    baseline && candidate
      ? {
          baseline,
          candidate,
          baseline_variant: q.get("baseline_variant") || undefined,
          candidate_variant: q.get("candidate_variant") || undefined,
          tolerance: tolerance ? Number(tolerance) : undefined,
        }
      : null;
  const { data, isLoading, error, refetch } = useComparison(params);

  return (
    <>
      <PageHeader
        title="Compare"
        description="Diff two experiments (or two variants) to catch regressions before shipping a prompt or model change."
      />
      <Card className="mb-6 p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <Picker
            label="Baseline"
            expId={baseline}
            variantId={q.get("baseline_variant")}
            onExp={(id) => q.set({ baseline: id, baseline_variant: null })}
            onVariant={(id) => q.set({ baseline_variant: id })}
          />
          <Button
            variant="ghost"
            aria-label="Swap baseline and candidate"
            title="Swap"
            className="self-center lg:mb-0.5"
            icon={<ArrowLeftRight className="size-4" />}
            onClick={() =>
              q.set({
                baseline: candidate,
                candidate: baseline,
                baseline_variant: q.get("candidate_variant"),
                candidate_variant: q.get("baseline_variant"),
              })
            }
          />
          <Picker
            label="Candidate"
            expId={candidate}
            variantId={q.get("candidate_variant")}
            onExp={(id) => q.set({ candidate: id, candidate_variant: null })}
            onVariant={(id) => q.set({ candidate_variant: id })}
          />
          <Field label="Tolerance" htmlFor="tolerance" className="w-28 shrink-0">
            <Select
              id="tolerance"
              value={tolerance || "0.02"}
              onChange={(e) => q.set({ tolerance: e.target.value === "0.02" ? null : e.target.value })}
              options={["0", "0.01", "0.02", "0.05", "0.1"].map((v) => ({ value: v, label: v }))}
            />
          </Field>
        </div>
      </Card>

      {!params ? (
        <Card>
          <EmptyState
            icon={<GitCompareArrows className="size-5" />}
            title="Pick two experiments"
            description="Choose a baseline and a candidate. Select variants of the same experiment to compare, for example, prompt v1 against v2 on the same model."
          />
        </Card>
      ) : isLoading ? (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
          <Card>
            <SkeletonRows rows={8} cols={5} />
          </Card>
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : data ? (
        <Results key={JSON.stringify(params)} c={data} />
      ) : null}
    </>
  );
}
