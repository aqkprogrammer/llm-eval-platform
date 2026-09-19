import { useState, type FormEvent } from "react";
import { Boxes, Plus, Trash2 } from "lucide-react";
import { useCreateModel, useDeleteModel, useModels, useProviders } from "../api/queries";
import type { ModelConfig, ProviderName } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState, InlineError } from "../components/ui/ErrorState";
import { Field, Input, Select, Textarea } from "../components/ui/Field";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton, SkeletonRows } from "../components/ui/Skeleton";
import { TBody, THead, Table, Td, Th, Tr } from "../components/ui/Table";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { relativeTime } from "../lib/format";

const PROVIDERS: ProviderName[] = ["mock", "anthropic", "openai", "ollama"];
const MODEL_HINT: Record<ProviderName, string> = {
  mock: "mock-gpt-large, mock-fast-small, mock-llama-base",
  anthropic: "claude-sonnet-5, claude-haiku-4-5, claude-opus-5",
  openai: "gpt-4.1, gpt-4.1-mini, gpt-4o-mini",
  ollama: "llama3.2, qwen2.5, mistral",
};

function CreateModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateModel();
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<ProviderName>("mock");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState("0");
  const [maxTokens, setMaxTokens] = useState("512");
  const [params, setParams] = useState("{}");
  const [err, setErr] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    let parsed: Record<string, unknown>;
    try {
      const p: unknown = JSON.parse(params || "{}");
      if (!p || typeof p !== "object" || Array.isArray(p)) throw new Error();
      parsed = p as Record<string, unknown>;
    } catch {
      return setErr("Params must be a JSON object.");
    }
    if (!name.trim() || !model.trim()) return setErr("Name and model are required.");
    create.mutate(
      {
        name: name.trim(),
        provider,
        model: model.trim(),
        temperature: temperature.trim() === "" ? null : Number(temperature),
        max_tokens: Number(maxTokens) || 512,
        params: parsed,
      },
      {
        onSuccess: () => {
          onClose();
          setName("");
          setModel("");
        },
      },
    );
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New model config"
      description="A named provider + model + sampling settings that experiments can target."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="model-form" loading={create.isPending}>
            Create
          </Button>
        </>
      }
    >
      <form id="model-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" htmlFor="m-name" required>
          <Input id="m-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="sonnet-precise" autoFocus />
        </Field>
        <Field label="Provider" htmlFor="m-provider" required>
          <Select
            id="m-provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as ProviderName)}
            options={PROVIDERS.map((p) => ({ value: p, label: p }))}
          />
        </Field>
        <Field label="Model" htmlFor="m-model" required hint={`e.g. ${MODEL_HINT[provider]}`} className="sm:col-span-2">
          <Input id="m-model" value={model} onChange={(e) => setModel(e.target.value)} />
        </Field>
        <Field label="Temperature" htmlFor="m-temp" hint="0 to 2. Leave empty for the provider default.">
          <Input id="m-temp" type="number" min={0} max={2} step={0.1} value={temperature} onChange={(e) => setTemperature(e.target.value)} />
        </Field>
        <Field label="Max tokens" htmlFor="m-max">
          <Input id="m-max" type="number" min={1} max={64000} value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} />
        </Field>
        <Field label="Extra params (JSON)" htmlFor="m-params" className="sm:col-span-2" hint='Passed to the provider, e.g. {"top_p": 0.9}'>
          <Textarea id="m-params" mono rows={3} value={params} onChange={(e) => setParams(e.target.value)} />
        </Field>
        {(err || create.error) && (
          <div className="sm:col-span-2">
            <InlineError error={err ?? create.error} />
          </div>
        )}
      </form>
    </Modal>
  );
}

function ConfirmDelete({ model, onClose }: { model: ModelConfig | null; onClose: () => void }) {
  const del = useDeleteModel();
  return (
    <Modal
      open={!!model}
      onClose={onClose}
      title="Delete model config?"
      className="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={del.isPending}
            onClick={() => model && del.mutate(model.id, { onSuccess: onClose })}
          >
            Delete
          </Button>
        </>
      }
    >
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        <span className="font-medium text-zinc-900 dark:text-zinc-100">{model?.name}</span> will no longer be selectable for new
        experiments. Past experiment results keep their snapshot.
      </p>
      {del.error && (
        <div className="mt-3">
          <InlineError error={del.error} />
        </div>
      )}
    </Modal>
  );
}

function ProvidersCard() {
  const { data, isLoading, error } = useProviders();
  const pricing = Object.entries(data?.pricing ?? {}).sort((a, b) => a[0].localeCompare(b[0]));
  return (
    <Card>
      <CardHeader title="Providers and pricing" description="USD per 1M tokens, used to compute cost_usd" />
      {isLoading ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-6" />
          <Skeleton className="h-40" />
        </div>
      ) : error ? (
        <div className="p-4">
          <ErrorState error={error} />
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2 border-b border-zinc-100 px-4 py-3 dark:border-zinc-800/70">
            {data?.providers.map((p) => (
              <Badge key={p.name} tone={p.configured ? "success" : "neutral"} dot>
                {p.name}: {p.configured ? "configured" : "not configured"}
              </Badge>
            ))}
          </div>
          <Table>
            <THead>
              <tr>
                <Th>Model</Th>
                <Th className="text-right">Input</Th>
                <Th className="text-right">Output</Th>
              </tr>
            </THead>
            <TBody>
              {pricing.map(([m, p]) => (
                <Tr key={m}>
                  <Td className="font-mono text-xs">{m}</Td>
                  <Td className="tabular text-right font-mono text-xs">${p.input.toFixed(2)}</Td>
                  <Td className="tabular text-right font-mono text-xs">${p.output.toFixed(2)}</Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        </>
      )}
    </Card>
  );
}

export default function ModelsPage() {
  useDocumentTitle("Models");
  const { data, isLoading, error, refetch } = useModels();
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<ModelConfig | null>(null);
  return (
    <>
      <PageHeader
        title="Models"
        description="Model configurations available to experiments. Provider credentials come from server environment variables."
        actions={
          <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
            New model config
          </Button>
        }
      />
      <div className="grid items-start gap-6 xl:grid-cols-[1fr_380px] [&>*]:min-w-0">
        <Card>
          {isLoading ? (
            <SkeletonRows rows={6} cols={5} />
          ) : error ? (
            <div className="p-4">
              <ErrorState error={error} onRetry={() => void refetch()} />
            </div>
          ) : !data?.length ? (
            <EmptyState
              icon={<Boxes className="size-5" />}
              title="No model configs"
              description="Add a config for the mock provider to try the platform without API keys."
              action={
                <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
                  New model config
                </Button>
              }
            />
          ) : (
            <Table>
              <THead>
                <tr>
                  <Th>Name</Th>
                  <Th>Provider</Th>
                  <Th>Model</Th>
                  <Th className="text-right">Temp</Th>
                  <Th className="text-right">Max tokens</Th>
                  <Th>Params</Th>
                  <Th>Created</Th>
                  <Th className="w-10">
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </THead>
              <TBody>
                {data.map((m) => (
                  <Tr key={m.id}>
                    <Td className="font-medium whitespace-nowrap text-zinc-900 dark:text-zinc-100">{m.name}</Td>
                    <Td>
                      <div className="flex items-center gap-1 whitespace-nowrap">
                        <Badge>{m.provider}</Badge>
                        {!m.available && <Badge tone="warning">not configured</Badge>}
                      </div>
                    </Td>
                    <Td className="font-mono text-xs whitespace-nowrap">{m.model}</Td>
                    <Td className="tabular text-right">{m.temperature ?? "default"}</Td>
                    <Td className="tabular text-right">{m.max_tokens.toLocaleString()}</Td>
                    <Td className="max-w-40 truncate font-mono text-xs text-zinc-500">
                      {Object.keys(m.params).length ? JSON.stringify(m.params) : "—"}
                    </Td>
                    <Td className="whitespace-nowrap text-zinc-500">{relativeTime(m.created_at)}</Td>
                    <Td>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Delete ${m.name}`}
                        onClick={() => setDeleting(m)}
                        icon={<Trash2 className="size-3.5" />}
                      />
                    </Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          )}
        </Card>
        <ProvidersCard />
      </div>
      <CreateModal open={creating} onClose={() => setCreating(false)} />
      <ConfirmDelete model={deleting} onClose={() => setDeleting(null)} />
    </>
  );
}
