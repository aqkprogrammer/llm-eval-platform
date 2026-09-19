import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import type { MetricScore } from "../../api/types";
import { useMetricIndex } from "../../hooks/useMetricIndex";
import { cn } from "../../lib/cn";
import { fmtMetric } from "../../lib/format";
import { CATEGORY_LABEL, categoryRank } from "../../lib/metrics";
import { Badge } from "../ui/Badge";
import { Collapsible, JsonView } from "../ui/CodeBlock";

interface Claim {
  claim: string;
  supported: boolean;
  reason?: string;
  coverage?: number;
}

function isClaimList(v: unknown): v is Claim[] {
  return Array.isArray(v) && v.every((c) => c && typeof c === "object" && "claim" in c && "supported" in c);
}

function Claims({ claims }: { claims: Claim[] }) {
  const supported = claims.filter((c) => c.supported).length;
  return (
    <div className="mt-2">
      <div className="mb-1.5 text-[11px] font-medium text-zinc-500 dark:text-zinc-400">
        {supported}/{claims.length} claims supported by the context
      </div>
      <ul className="space-y-1.5">
        {claims.map((c, i) => (
          <li
            key={i}
            className={cn(
              "flex gap-2 rounded-md border px-2.5 py-2 text-xs",
              c.supported
                ? "border-emerald-200 bg-emerald-50/60 dark:border-emerald-500/20 dark:bg-emerald-500/5"
                : "border-rose-200 bg-rose-50/60 dark:border-rose-500/20 dark:bg-rose-500/5",
            )}
          >
            {c.supported ? (
              <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-label="Supported" />
            ) : (
              <XCircle className="mt-0.5 size-3.5 shrink-0 text-rose-600 dark:text-rose-400" aria-label="Unsupported" />
            )}
            <div className="min-w-0">
              <p className="text-zinc-800 dark:text-zinc-200">{c.claim}</p>
              {c.reason && <p className="mt-0.5 text-zinc-500 dark:text-zinc-400">{c.reason}</p>}
            </div>
            {typeof c.coverage === "number" && (
              <span className="tabular ml-auto shrink-0 font-mono text-[11px] text-zinc-500">{c.coverage.toFixed(2)}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ListChips({ label, items }: { label: string; items: unknown[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
      <span className="text-zinc-500 dark:text-zinc-400">{label}:</span>
      {items.map((it, i) => (
        <code key={i} className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] dark:bg-zinc-800">
          {typeof it === "string" ? it : JSON.stringify(it)}
        </code>
      ))}
    </div>
  );
}

export function ScoreItem({ score }: { score: MetricScore }) {
  const index = useMetricIndex();
  const info = index.get(score.metric);
  const details = score.details ?? {};
  const claims = isClaimList(details.claims) ? details.claims : null;
  const listEntries = Object.entries(details).filter(
    ([k, v]) => k !== "claims" && Array.isArray(v) && (v as unknown[]).length > 0,
  ) as [string, unknown[]][];
  const hasDetails = Object.keys(details).length > 0;
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      <div className="flex flex-wrap items-center gap-2">
        {score.passed === true ? (
          <CheckCircle2 className="size-4 text-emerald-500" aria-label="Passed" />
        ) : score.passed === false ? (
          <XCircle className="size-4 text-rose-500" aria-label="Failed" />
        ) : (
          <CircleDashed className="size-4 text-zinc-400" aria-label="No threshold" />
        )}
        <span className="font-mono text-sm font-medium text-zinc-900 dark:text-zinc-100">{score.metric}</span>
        <Badge tone="neutral">{CATEGORY_LABEL[score.category] ?? score.category}</Badge>
        <span
          className={cn(
            "tabular ml-auto font-mono text-sm font-semibold",
            score.passed === true && "text-emerald-600 dark:text-emerald-400",
            score.passed === false && "text-rose-600 dark:text-rose-400",
          )}
        >
          {fmtMetric(score.value, info?.unit)}
        </span>
      </div>
      {score.explanation && <p className="mt-1.5 text-xs text-zinc-600 dark:text-zinc-400">{score.explanation}</p>}
      {score.error && <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">Error: {score.error}</p>}
      {claims && <Claims claims={claims} />}
      {listEntries.map(([k, v]) => (
        <ListChips key={k} label={k.replace(/_/g, " ")} items={v} />
      ))}
      {hasDetails && (
        <div className="mt-2">
          <Collapsible title="Details JSON">
            <JsonView value={details} />
          </Collapsible>
        </div>
      )}
    </div>
  );
}

export function ScoreList({ scores }: { scores: MetricScore[] }) {
  const sorted = [...scores].sort(
    (a, b) => categoryRank(a.category) - categoryRank(b.category) || a.metric.localeCompare(b.metric),
  );
  const failed = scores.filter((s) => s.passed === false).length;
  return (
    <div>
      <div className="mb-2 text-xs text-zinc-500 dark:text-zinc-400">
        {scores.length} metrics, {failed ? <span className="text-rose-600 dark:text-rose-400">{failed} failing</span> : "none failing"}
      </div>
      <div className="grid gap-2">
        {sorted.map((s) => (
          <ScoreItem key={s.metric} score={s} />
        ))}
      </div>
    </div>
  );
}
