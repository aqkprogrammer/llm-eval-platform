import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, Download, FlaskConical } from "lucide-react";
import { buildUrl } from "../api/client";
import { useDataset } from "../api/queries";
import type { TestCase } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { JsonView } from "../components/ui/CodeBlock";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Drawer } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { ContextList, Section, TextPanel } from "../components/ui/Panels";
import { Skeleton, SkeletonRows } from "../components/ui/Skeleton";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { fmtDateTime, fmtInt } from "../lib/format";

const linkBtn =
  "inline-flex h-8.5 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3.5 text-sm font-medium text-zinc-800 shadow-xs hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800";

export default function DatasetDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error, refetch } = useDataset(id);
  const [selected, setSelected] = useState<TestCase | null>(null);
  useDocumentTitle(data?.name ?? "Dataset");

  if (isLoading)
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Card>
          <SkeletonRows rows={8} cols={4} />
        </Card>
      </div>
    );
  if (error || !data) return <ErrorState error={error ?? "Dataset not found"} onRetry={() => void refetch()} />;

  return (
    <>
      <PageHeader
        breadcrumb={
          <span className="flex items-center gap-1">
            <Link to="/datasets" className="hover:text-zinc-900 dark:hover:text-zinc-100">
              Datasets
            </Link>
            <ChevronRight className="size-3" />
            <span>{data.name}</span>
          </span>
        }
        title={data.name}
        description={
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {data.description && <span>{data.description}</span>}
            <span>{fmtInt(data.case_count)} cases</span>
            <span>created {fmtDateTime(data.created_at)}</span>
            {data.tags.map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </span>
        }
        actions={
          <>
            <a href={buildUrl(`/datasets/${data.id}/export`, { format: "jsonl" })} className={linkBtn} download={`${data.name}.jsonl`}>
              <Download className="size-4" /> Export JSONL
            </a>
            <Link to="/experiments?new=1" className={linkBtn}>
              <FlaskConical className="size-4" /> Evaluate
            </Link>
          </>
        }
      />
      <Card>
        {data.cases.length === 0 ? (
          <EmptyState title="This dataset has no cases" description="Append cases via POST /api/datasets/{id}/cases." />
        ) : (
          <Table className="table-fixed">
            <THead>
              <tr>
                <Th className="w-12">#</Th>
                <Th className="w-[38%]">Input</Th>
                <Th className="w-20 text-right">Context</Th>
                <Th>Expected output</Th>
                <Th className="w-44">Tags</Th>
              </tr>
            </THead>
            <TBody>
              {data.cases.map((c) => (
                <Tr
                  key={c.id}
                  interactive
                  tabIndex={0}
                  onClick={() => setSelected(c)}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(c)}
                >
                  <Td className="tabular align-top text-zinc-400">{c.position + 1}</Td>
                  <Td className="align-top">
                    <span className="line-clamp-2 text-zinc-800 dark:text-zinc-200">{c.input}</span>
                  </Td>
                  <Td className="tabular text-right align-top text-zinc-500">{c.context.length}</Td>
                  <Td className="align-top">
                    <span className="line-clamp-2 text-zinc-600 dark:text-zinc-400">{c.expected_output ?? "—"}</span>
                  </Td>
                  <Td className="align-top">
                    <div className="flex flex-wrap gap-1">
                      {c.tags.map((t) => (
                        <Badge key={t}>{t}</Badge>
                      ))}
                    </div>
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `Case ${selected.position + 1}` : ""}
        className="max-w-2xl"
      >
        {selected && (
          <div className="space-y-6">
            <Section title="Input">
              <TextPanel>{selected.input}</TextPanel>
            </Section>
            <Section title={`Context (${selected.context.length})`}>
              <ContextList items={selected.context} />
            </Section>
            <Section title="Expected output">
              {selected.expected_output ? <TextPanel>{selected.expected_output}</TextPanel> : <p className="text-sm text-zinc-500 italic">None</p>}
            </Section>
            <Section title="Metadata">
              <JsonView value={selected.metadata} />
            </Section>
          </div>
        )}
      </Drawer>
    </>
  );
}
