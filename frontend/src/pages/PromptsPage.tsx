import { useMemo, useState } from "react";
import { FileText, GitBranch, Plus } from "lucide-react";
import { useCreatePrompt, useCreatePromptVersion, usePrompts } from "../api/queries";
import type { PromptTemplate, PromptVersion } from "../api/types";
import { LineDiff } from "../components/prompts/LineDiff";
import { PromptEditor } from "../components/prompts/PromptEditor";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { CodeBlock } from "../components/ui/CodeBlock";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Field, Select } from "../components/ui/Field";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useQueryParams } from "../hooks/useSearchParam";
import { cn } from "../lib/cn";
import { fmtDateTime, relativeTime } from "../lib/format";

function VersionView({ v }: { v: PromptVersion }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-500 dark:text-zinc-400">
        <span title={fmtDateTime(v.created_at)}>Created {relativeTime(v.created_at)}</span>
        <span className="font-mono">id {v.id.slice(0, 8)}</span>
        {v.variables.length > 0 && (
          <span className="flex flex-wrap items-center gap-1">
            Variables:
            {v.variables.map((x) => (
              <Badge key={x} tone="accent">
                {x}
              </Badge>
            ))}
          </span>
        )}
      </div>
      {v.notes && (
        <p className="rounded-md border-l-2 border-accent-400 bg-accent-50/50 px-3 py-2 text-sm text-zinc-700 dark:bg-accent-500/5 dark:text-zinc-300">
          {v.notes}
        </p>
      )}
      <CodeBlock label="System prompt">{v.system_prompt}</CodeBlock>
      <CodeBlock label="User template">{v.user_template}</CodeBlock>
    </div>
  );
}

function DiffView({ t }: { t: PromptTemplate }) {
  const versions = t.versions;
  const [from, setFrom] = useState(versions.length > 1 ? versions[versions.length - 2].id : versions[0].id);
  const [to, setTo] = useState(versions[versions.length - 1].id);
  const a = versions.find((v) => v.id === from) ?? versions[0];
  const b = versions.find((v) => v.id === to) ?? versions[versions.length - 1];
  const options = versions.map((v) => ({ value: v.id, label: `v${v.version}${v.notes ? ` - ${v.notes}` : ""}` }));
  if (versions.length < 2)
    return <EmptyState title="Only one version" description="Create a new version to compare changes line by line." />;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="From" htmlFor="diff-from">
          <Select id="diff-from" value={from} onChange={(e) => setFrom(e.target.value)} options={options} />
        </Field>
        <Field label="To" htmlFor="diff-to">
          <Select id="diff-to" value={to} onChange={(e) => setTo(e.target.value)} options={options} />
        </Field>
      </div>
      <LineDiff label="System prompt" before={a.system_prompt} after={b.system_prompt} />
      <LineDiff label="User template" before={a.user_template} after={b.user_template} />
      {(a.notes || b.notes) && <LineDiff label="Notes" before={a.notes} after={b.notes} />}
    </div>
  );
}

function TemplateDetail({ t, versionId, onVersion }: { t: PromptTemplate; versionId: string; onVersion: (id: string) => void }) {
  const [mode, setMode] = useState<"view" | "diff">("view");
  const [editing, setEditing] = useState(false);
  const create = useCreatePromptVersion(t.id);
  const sorted = useMemo(() => [...t.versions].sort((a, b) => b.version - a.version), [t.versions]);
  const current = sorted.find((v) => v.id === versionId) ?? sorted[0];
  const latest = sorted[0];

  return (
    <Card className="min-w-0">
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            {t.name}
            <Badge tone="neutral">{t.versions.length} versions</Badge>
          </span>
        }
        description={t.description || undefined}
        actions={
          <>
            <Tabs
              ariaLabel="View mode"
              value={mode}
              onChange={setMode}
              items={[
                { value: "view", label: "Version" },
                { value: "diff", label: "Diff" },
              ]}
            />
            <Button size="sm" variant="primary" icon={<GitBranch className="size-3.5" />} onClick={() => setEditing(true)}>
              New version
            </Button>
          </>
        }
      />
      <div className="p-4">
        {mode === "view" ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Versions">
              {sorted.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  role="tab"
                  aria-selected={v.id === current?.id}
                  onClick={() => onVersion(v.id)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 font-mono text-xs transition-colors",
                    v.id === current?.id
                      ? "border-accent-300 bg-accent-50 text-accent-700 dark:border-accent-500/40 dark:bg-accent-500/10 dark:text-accent-300"
                      : "border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900",
                  )}
                >
                  v{v.version}
                  {v.id === latest.id && <span className="ml-1 font-sans text-[10px] opacity-70">latest</span>}
                </button>
              ))}
            </div>
            {current && <VersionView v={current} />}
          </div>
        ) : (
          <DiffView key={t.id} t={{ ...t, versions: [...t.versions].sort((a, b) => a.version - b.version) }} />
        )}
      </div>
      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title={`New version of ${t.name}`}
        description={`Starts from v${latest.version}. Saved as v${latest.version + 1}.`}
        className="max-w-6xl"
      >
        {editing && (
          <PromptEditor
            initial={{ system_prompt: latest.system_prompt, user_template: latest.user_template, notes: "" }}
            submitLabel="Save version"
            pending={create.isPending}
            error={create.error}
            onCancel={() => setEditing(false)}
            onSubmit={(d) =>
              create.mutate(
                { system_prompt: d.system_prompt, user_template: d.user_template, notes: d.notes },
                {
                  onSuccess: (v) => {
                    setEditing(false);
                    onVersion(v.id);
                  },
                },
              )
            }
          />
        )}
      </Modal>
    </Card>
  );
}

export default function PromptsPage() {
  useDocumentTitle("Prompts");
  const q = useQueryParams<"template" | "version">();
  const { data, isLoading, error, refetch } = usePrompts();
  const [creating, setCreating] = useState(false);
  const createTemplate = useCreatePrompt();
  const selected = data?.find((t) => t.id === q.get("template")) ?? data?.[0];

  return (
    <>
      <PageHeader
        title="Prompts"
        description="Versioned prompt templates. Every version is immutable so experiments stay reproducible."
        actions={
          <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
            New template
          </Button>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <Skeleton className="h-64" />
          <Skeleton className="h-96" />
        </div>
      ) : !data?.length ? (
        <Card>
          <EmptyState
            icon={<FileText className="size-5" />}
            title="No prompt templates"
            description="Create a template with a system prompt and a user template to evaluate it."
            action={
              <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
                New template
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[260px_1fr] [&>*]:min-w-0">
          <Card>
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800/70" aria-label="Prompt templates">
              {data.map((t) => {
                const latest = t.versions.reduce((m, v) => (v.version > m.version ? v : m), t.versions[0]);
                const active = t.id === selected?.id;
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => q.set({ template: t.id, version: null })}
                      aria-current={active}
                      className={cn(
                        "block w-full px-4 py-3 text-left transition-colors",
                        active ? "bg-accent-50/70 dark:bg-accent-500/10" : "hover:bg-zinc-50 dark:hover:bg-zinc-900/60",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">{t.name}</span>
                        <span className="font-mono text-xs text-zinc-500">v{latest?.version}</span>
                      </div>
                      {t.description && <p className="mt-0.5 line-clamp-2 text-xs text-zinc-500 dark:text-zinc-400">{t.description}</p>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>
          {selected && (
            <TemplateDetail
              key={selected.id}
              t={selected}
              versionId={q.get("version")}
              onVersion={(id) => q.set({ template: selected.id, version: id })}
            />
          )}
        </div>
      )}
      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="New prompt template"
        description="Creates the template with version 1."
        className="max-w-6xl"
      >
        {creating && (
          <PromptEditor
            withName
            initial={{
              name: "",
              description: "",
              system_prompt: "You are a helpful assistant. Answer using only the provided context.",
              user_template: "Question: {{ input }}\n\nContext:\n{{ context_str }}\n\nAnswer:",
              notes: "Initial version",
            }}
            submitLabel="Create template"
            pending={createTemplate.isPending}
            error={createTemplate.error}
            onCancel={() => setCreating(false)}
            onSubmit={(d) =>
              createTemplate.mutate(
                {
                  name: d.name ?? "",
                  description: d.description ?? "",
                  system_prompt: d.system_prompt,
                  user_template: d.user_template,
                  notes: d.notes,
                },
                {
                  onSuccess: (t) => {
                    setCreating(false);
                    q.set({ template: t.id, version: null });
                  },
                },
              )
            }
          />
        )}
      </Modal>
    </>
  );
}
