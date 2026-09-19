import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Database, Upload } from "lucide-react";
import { useDatasets, useImportDataset } from "../api/queries";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { CodeBlock } from "../components/ui/CodeBlock";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState, InlineError } from "../components/ui/ErrorState";
import { Field, Input, Textarea } from "../components/ui/Field";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { fmtDateTime, fmtInt, relativeTime } from "../lib/format";

const FORMAT_EXAMPLE = `{"input": "How long do I have to return an item?", "context": ["Acme accepts returns within 30 days of delivery."], "expected_output": "Within 30 days of delivery.", "tags": ["returns"], "metadata": {"priority": "high"}}
{"input": "What is the capital of France?", "expected_output": "Paris"}`;

function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const mutation = useImportDataset();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [err, setErr] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!file) return setErr("Choose a .jsonl, .json or .csv file to import.");
    const form = new FormData();
    form.append("file", file);
    if (name.trim()) form.append("name", name.trim());
    form.append("description", description);
    mutation.mutate(form, { onSuccess: (ds) => navigate(`/datasets/${ds.id}`) });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Import dataset"
      description="Upload test cases as JSONL, JSON (array of objects) or CSV."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="import-form" loading={mutation.isPending} icon={<Upload className="size-4" />}>
            Import
          </Button>
        </>
      }
    >
      <form id="import-form" onSubmit={submit} className="space-y-4">
        <Field label="File" htmlFor="ds-file" required hint="Max 20 MB.">
          <input
            id="ds-file"
            type="file"
            accept=".jsonl,.ndjson,.json,.csv"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f && !name) setName(f.name.replace(/\.[^.]+$/, ""));
            }}
            className="block w-full text-sm text-zinc-600 file:mr-3 file:rounded-md file:border-0 file:bg-accent-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-accent-700 hover:file:bg-accent-100 dark:text-zinc-400 dark:file:bg-accent-500/15 dark:file:text-accent-300"
          />
        </Field>
        <Field label="Name" htmlFor="ds-name" hint="Defaults to the file name.">
          <Input id="ds-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="customer-support-qa" />
        </Field>
        <Field label="Description" htmlFor="ds-desc">
          <Textarea id="ds-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="space-y-2 rounded-md border border-zinc-200 p-3 text-xs text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
          <p className="font-medium text-zinc-800 dark:text-zinc-200">Format</p>
          <ul className="list-inside list-disc space-y-0.5">
            <li>
              <code className="font-mono">input</code> (required): the user question or task
            </li>
            <li>
              <code className="font-mono">context</code>: list of retrieved passages (enables faithfulness)
            </li>
            <li>
              <code className="font-mono">expected_output</code>: reference answer (enables correctness and similarity)
            </li>
            <li>
              <code className="font-mono">tags</code>: list of strings; <code className="font-mono">metadata</code>: free-form object
            </li>
            <li>
              In CSV, <code className="font-mono">context</code> is a JSON array or passages separated by blank lines;{" "}
              <code className="font-mono">tags</code> are comma or semicolon separated; <code className="font-mono">metadata</code> is a JSON object.
            </li>
          </ul>
          <CodeBlock label="Example JSONL">{FORMAT_EXAMPLE}</CodeBlock>
        </div>
        {(err || mutation.error) && <InlineError error={err ?? mutation.error} />}
      </form>
    </Modal>
  );
}

export default function DatasetsPage() {
  useDocumentTitle("Datasets");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useDatasets();
  return (
    <>
      <PageHeader
        title="Datasets"
        description="Versioned collections of test cases: inputs, retrieval context and reference answers."
        actions={
          <Button variant="primary" icon={<Upload className="size-4" />} onClick={() => setOpen(true)}>
            Import dataset
          </Button>
        }
      />
      <Card>
        {isLoading ? (
          <SkeletonRows rows={4} cols={4} />
        ) : error ? (
          <div className="p-4">
            <ErrorState error={error} onRetry={() => void refetch()} />
          </div>
        ) : !data?.length ? (
          <EmptyState
            icon={<Database className="size-5" />}
            title="No datasets"
            description="Import a JSONL, JSON or CSV file of test cases to start evaluating."
            action={
              <Button variant="primary" icon={<Upload className="size-4" />} onClick={() => setOpen(true)}>
                Import dataset
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th>Name</Th>
                <Th>Description</Th>
                <Th className="text-right">Cases</Th>
                <Th>Tags</Th>
                <Th>Created</Th>
              </tr>
            </THead>
            <TBody>
              {data.map((d) => {
                const go = () => navigate(`/datasets/${d.id}`);
                return (
                  <Tr key={d.id} interactive tabIndex={0} onClick={go} onKeyDown={(e) => e.key === "Enter" && go()}>
                    <Td className="font-medium text-zinc-900 dark:text-zinc-100">{d.name}</Td>
                    <Td className="max-w-md text-zinc-600 dark:text-zinc-400">
                      <span className="line-clamp-1">{d.description || "—"}</span>
                    </Td>
                    <Td className="tabular text-right">{fmtInt(d.case_count)}</Td>
                    <Td>
                      <div className="flex flex-wrap gap-1">
                        {d.tags.map((t) => (
                          <Badge key={t}>{t}</Badge>
                        ))}
                      </div>
                    </Td>
                    <Td className="whitespace-nowrap text-zinc-500" title={fmtDateTime(d.created_at)}>
                      {relativeTime(d.created_at)}
                    </Td>
                  </Tr>
                );
              })}
            </TBody>
          </Table>
        )}
      </Card>
      <ImportModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
