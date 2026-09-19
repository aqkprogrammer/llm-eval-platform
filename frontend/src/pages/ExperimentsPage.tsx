import { useNavigate, useSearchParams } from "react-router-dom";
import { FlaskConical, Plus } from "lucide-react";
import { useExperiments } from "../api/queries";
import { NewExperimentModal } from "../components/experiments/NewExperimentModal";
import { GateBadge, StatusBadge } from "../components/StatusBadges";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Progress } from "../components/ui/Progress";
import { SkeletonRows } from "../components/ui/Skeleton";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { fmtDateTime, fmtDuration, fmtInt, relativeTime } from "../lib/format";

export default function ExperimentsPage() {
  useDocumentTitle("Experiments");
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const open = params.get("new") === "1";
  const setOpen = (v: boolean) =>
    setParams(
      (p) => {
        const n = new URLSearchParams(p);
        if (v) n.set("new", "1");
        else n.delete("new");
        return n;
      },
      { replace: true },
    );
  const { data, isLoading, error, refetch } = useExperiments(200);

  return (
    <>
      <PageHeader
        title="Experiments"
        description="Each experiment runs a prompts x models matrix over a dataset and scores every output."
        actions={
          <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setOpen(true)}>
            New experiment
          </Button>
        }
      />
      <Card>
        {isLoading ? (
          <SkeletonRows rows={6} cols={6} />
        ) : error ? (
          <div className="p-4">
            <ErrorState error={error} onRetry={() => void refetch()} />
          </div>
        ) : !data?.length ? (
          <EmptyState
            icon={<FlaskConical className="size-5" />}
            title="No experiments yet"
            description="Pick a dataset, one or more prompt versions and models, and the metrics to score them with."
            action={
              <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setOpen(true)}>
                New experiment
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th>Name</Th>
                <Th>Dataset</Th>
                <Th className="w-56">Status</Th>
                <Th className="text-right">Variants</Th>
                <Th>Gates</Th>
                <Th>Duration</Th>
                <Th>Created</Th>
              </tr>
            </THead>
            <TBody>
              {data.map((e) => {
                const active = e.status === "running" || e.status === "queued";
                const go = () => navigate(`/experiments/${e.id}`);
                return (
                  <Tr
                    key={e.id}
                    interactive
                    tabIndex={0}
                    onClick={go}
                    onKeyDown={(ev) => ev.key === "Enter" && go()}
                  >
                    <Td className="max-w-80">
                      <div className="truncate font-medium text-zinc-900 dark:text-zinc-100">{e.name}</div>
                      {e.error && <div className="truncate text-xs text-rose-600 dark:text-rose-400">{e.error}</div>}
                    </Td>
                    <Td className="text-zinc-600 dark:text-zinc-400">{e.dataset_name ?? "—"}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={e.status} />
                        <div className="flex-1">
                          <Progress
                            value={e.progress_done}
                            max={e.progress_total || 1}
                            tone={e.status === "completed" ? (e.progress_failed ? "danger" : "success") : active ? "accent" : "neutral"}
                            label={`${e.name} progress`}
                          />
                        </div>
                        <span className="tabular text-xs text-zinc-500">
                          {fmtInt(e.progress_done)}/{fmtInt(e.progress_total)}
                        </span>
                      </div>
                    </Td>
                    <Td className="tabular text-right">{e.variant_count}</Td>
                    <Td>{e.status === "completed" ? <GateBadge passed={e.gate_passed} compact /> : "—"}</Td>
                    <Td className="tabular text-zinc-600 dark:text-zinc-400">{fmtDuration(e.started_at, e.finished_at)}</Td>
                    <Td className="whitespace-nowrap text-zinc-600 dark:text-zinc-400" title={fmtDateTime(e.created_at)}>
                      {relativeTime(e.created_at)}
                    </Td>
                  </Tr>
                );
              })}
            </TBody>
          </Table>
        )}
      </Card>
      <NewExperimentModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
