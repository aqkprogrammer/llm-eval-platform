import { Link, useParams } from "react-router-dom";
import { ChevronRight, Flag, Loader2 } from "lucide-react";
import { useTrace } from "../api/queries";
import { ScoreList } from "../components/experiments/ScoreList";
import { ScoreStatusBadge } from "../components/StatusBadges";
import { Waterfall } from "../components/traces/Waterfall";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader } from "../components/ui/Card";
import { JsonView } from "../components/ui/CodeBlock";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { ContextList, Section, StatsRow, TextPanel } from "../components/ui/Panels";
import { Skeleton } from "../components/ui/Skeleton";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { fmtDateTime, fmtMs, fmtTokens, fmtUsd, shortId } from "../lib/format";

export default function TraceDetailPage() {
  const { id } = useParams();
  const { data: t, isLoading, error, refetch } = useTrace(id);
  useDocumentTitle(t ? `Trace ${shortId(t.id)}` : "Trace");

  if (isLoading)
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-16" />
        <Skeleton className="h-64" />
      </div>
    );
  if (error || !t) return <ErrorState error={error ?? "Trace not found"} onRetry={() => void refetch()} />;

  const scoring = t.score_status === "pending" || t.score_status === "running";
  const hasMeta = Object.keys(t.metadata ?? {}).length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <span className="flex items-center gap-1">
            <Link to="/traces" className="hover:text-zinc-900 dark:hover:text-zinc-100">
              Traces
            </Link>
            <ChevronRight className="size-3" />
            <span className="font-mono">{shortId(t.id)}</span>
          </span>
        }
        title={
          <span className="flex flex-wrap items-center gap-2.5">
            {t.name}
            <Badge tone={t.source === "production" ? "info" : "accent"}>{t.source}</Badge>
            {t.status === "error" && <Badge tone="danger">error</Badge>}
            {t.flagged && (
              <Badge tone="danger" icon={<Flag className="size-3" />}>
                flagged
              </Badge>
            )}
          </span>
        }
        description={
          <span className="flex flex-wrap gap-x-4 gap-y-1">
            <span>{fmtDateTime(t.start_time)}</span>
            {t.provider && (
              <span>
                {t.provider} / <span className="font-mono">{t.model}</span>
              </span>
            )}
            {t.user_id && <span>user {t.user_id}</span>}
            {t.session_id && <span>session {t.session_id}</span>}
            {t.experiment_id && (
              <Link to={`/experiments/${t.experiment_id}`} className="text-accent-600 hover:underline dark:text-accent-400">
                View experiment
              </Link>
            )}
            {t.tags.map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </span>
        }
      />
      <StatsRow
        items={[
          { label: "Latency", value: fmtMs(t.latency_ms) },
          { label: "Time to first token", value: fmtMs(t.ttft_ms) },
          { label: "Tokens (in / out)", value: `${fmtTokens(t.input_tokens)} / ${fmtTokens(t.output_tokens)}` },
          { label: "Cost", value: fmtUsd(t.cost_usd) },
        ]}
      />
      <Card>
        <CardHeader title="Waterfall" description="Spans nested by parent; click a span to inspect its attributes" />
        <Waterfall spans={t.spans} />
      </Card>
      <div className="grid items-start gap-6 xl:grid-cols-2 [&>*]:min-w-0">
        <Card>
          <CardHeader title="Input and output" />
          <div className="space-y-5 p-4">
            <Section title="Input">
              <TextPanel>{t.input ?? ""}</TextPanel>
            </Section>
            <Section title={`Context (${t.context.length})`}>
              <ContextList items={t.context} />
            </Section>
            <Section title="Output">
              <TextPanel tone={t.status === "error" ? "danger" : undefined}>{t.output ?? ""}</TextPanel>
            </Section>
            {hasMeta && (
              <Section title="Metadata">
                <JsonView value={t.metadata} />
              </Section>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader
            title="Scores"
            description={t.source === "production" ? "Asynchronous monitoring scores" : "Scores from the experiment run"}
            actions={<ScoreStatusBadge status={t.score_status} />}
          />
          <div className="p-4">
            {scoring ? (
              <EmptyState
                icon={<Loader2 className="size-5 animate-spin" />}
                title="Scoring pending"
                description="Monitoring metrics are computed in the background. This page refreshes automatically."
              />
            ) : t.scores.length === 0 ? (
              <EmptyState
                title="No scores"
                description={
                  t.score_status === "failed"
                    ? "Scoring failed for this trace. Check the server logs."
                    : t.source === "experiment"
                      ? "Experiment scores are attached to the case result. Open the experiment and click the case to see them."
                      : "This trace was ingested without monitoring metrics."
                }
                action={
                  t.experiment_id ? (
                    <Link to={`/experiments/${t.experiment_id}`} className="text-sm font-medium text-accent-600 hover:underline dark:text-accent-400">
                      Open experiment
                    </Link>
                  ) : undefined
                }
              />
            ) : (
              <ScoreList scores={t.scores} />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
