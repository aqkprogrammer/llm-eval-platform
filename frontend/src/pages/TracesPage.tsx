import { useNavigate } from "react-router-dom";
import { Flag, Waypoints } from "lucide-react";
import { useTraces } from "../api/queries";
import { ScoreStatusBadge } from "../components/StatusBadges";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Checkbox } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { Pagination } from "../components/ui/Pagination";
import { SkeletonRows } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useQueryParams } from "../hooks/useSearchParam";
import { cn } from "../lib/cn";
import { fmtDateTime, fmtMs, fmtTokens, fmtUsd, relativeTime } from "../lib/format";

const PAGE = 50;

export default function TracesPage() {
  useDocumentTitle("Traces");
  const navigate = useNavigate();
  const q = useQueryParams<"source" | "flagged" | "offset" | "model">();
  const source = q.get("source") || "all";
  const flagged = q.get("flagged") === "1";
  const offset = Number(q.get("offset")) || 0;
  const model = q.get("model");
  const { data, isLoading, isFetching, error, refetch } = useTraces({
    source: source === "all" ? undefined : source,
    flagged: flagged ? true : undefined,
    model: model || undefined,
    limit: PAGE,
    offset,
  });

  return (
    <>
      <PageHeader
        title="Traces"
        description="Every LLM call, from experiment runs and from production apps instrumented with the SDK."
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-zinc-100 px-4 py-3 dark:border-zinc-800/70">
          <Tabs
            ariaLabel="Trace source"
            value={source}
            onChange={(v) => q.set({ source: v === "all" ? null : v, offset: null })}
            items={[
              { value: "all", label: "All" },
              { value: "production", label: "Production" },
              { value: "experiment", label: "Experiment" },
            ]}
          />
          <Checkbox
            label="Flagged only"
            checked={flagged}
            onChange={(e) => q.set({ flagged: e.target.checked ? "1" : null, offset: null })}
          />
          {model && (
            <button
              type="button"
              onClick={() => q.set({ model: null, offset: null })}
              className="text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              model: <span className="font-mono">{model}</span> (clear)
            </button>
          )}
          {data && <span className="tabular ml-auto text-xs text-zinc-500">{data.total.toLocaleString()} traces</span>}
        </div>
        {isLoading ? (
          <SkeletonRows rows={10} cols={7} />
        ) : error ? (
          <div className="p-4">
            <ErrorState error={error} onRetry={() => void refetch()} />
          </div>
        ) : !data?.items.length ? (
          <EmptyState
            icon={<Waypoints className="size-5" />}
            title="No traces match"
            description={
              flagged
                ? "No traces failed a monitored metric. Clear the flagged filter to see all traces."
                : "Send production traces with the @observe decorator or POST /api/traces, or run an experiment."
            }
          />
        ) : (
          <div className={cn("transition-opacity", isFetching && "opacity-70")}>
            <Table>
              <THead>
                <tr>
                  <Th>Time</Th>
                  <Th>Name</Th>
                  <Th>Source</Th>
                  <Th>Model</Th>
                  <Th className="text-right">Latency</Th>
                  <Th className="text-right">Tokens</Th>
                  <Th className="text-right">Cost</Th>
                  <Th>Scoring</Th>
                  <Th>
                    <span className="sr-only">Flags</span>
                  </Th>
                </tr>
              </THead>
              <TBody>
                {data.items.map((t) => {
                  const go = () => navigate(`/traces/${t.id}`);
                  return (
                    <Tr key={t.id} interactive tabIndex={0} onClick={go} onKeyDown={(e) => e.key === "Enter" && go()}>
                      <Td className="whitespace-nowrap text-zinc-500" title={fmtDateTime(t.start_time)}>
                        {relativeTime(t.start_time)}
                      </Td>
                      <Td className="max-w-72">
                        <div className="truncate font-medium text-zinc-900 dark:text-zinc-100">{t.name}</div>
                        <div className="truncate text-xs text-zinc-500">{t.input_preview}</div>
                      </Td>
                      <Td>
                        <Badge tone={t.source === "production" ? "info" : "accent"}>{t.source}</Badge>
                      </Td>
                      <Td className="font-mono text-xs whitespace-nowrap">{t.model ?? "—"}</Td>
                      <Td className="tabular text-right font-mono text-xs">{fmtMs(t.latency_ms)}</Td>
                      <Td className="tabular text-right font-mono text-xs">{fmtTokens(t.input_tokens + t.output_tokens)}</Td>
                      <Td className="tabular text-right font-mono text-xs">{fmtUsd(t.cost_usd)}</Td>
                      <Td>
                        <ScoreStatusBadge status={t.score_status} />
                      </Td>
                      <Td>
                        <div className="flex gap-1">
                          {t.flagged && (
                            <Badge tone="danger" icon={<Flag className="size-3" />}>
                              flagged
                            </Badge>
                          )}
                          {t.status === "error" && <Badge tone="danger">error</Badge>}
                        </div>
                      </Td>
                    </Tr>
                  );
                })}
              </TBody>
            </Table>
            <Pagination offset={offset} limit={PAGE} total={data.total} onChange={(o) => q.set({ offset: o ? String(o) : null })} />
          </div>
        )}
      </Card>
    </>
  );
}
