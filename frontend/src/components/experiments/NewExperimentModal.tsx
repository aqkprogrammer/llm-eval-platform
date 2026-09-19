import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Grid3x3, Plus, Trash2 } from "lucide-react";
import { useCreateExperiment, useDatasets, useMetrics, useModels, usePrompts } from "../../api/queries";
import type { MetricInfo } from "../../api/types";
import { cn } from "../../lib/cn";
import { fmtInt } from "../../lib/format";
import { CATEGORY_LABEL, DEFAULT_METRICS, categoryRank } from "../../lib/metrics";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { InlineError } from "../ui/ErrorState";
import { Checkbox, Field, Input, Select } from "../ui/Field";
import { Modal } from "../ui/Modal";
import { Skeleton } from "../ui/Skeleton";

function toggle(list: string[], v: string): string[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400">{children}</h3>
      {right}
    </div>
  );
}

interface ThresholdRow {
  key: number;
  metric: string;
  value: string;
}

function Form({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const datasets = useDatasets();
  const prompts = usePrompts();
  const models = useModels();
  const metrics = useMetrics();
  const create = useCreateExperiment();

  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [promptIds, setPromptIds] = useState<string[]>([]);
  const [modelIds, setModelIds] = useState<string[]>([]);
  const [selectedMetrics, setSelectedMetrics] = useState<string[] | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdRow[]>([]);
  const [concurrency, setConcurrency] = useState("");
  const [caseLimit, setCaseLimit] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const availableMetricNames = useMemo(
    () => new Set((metrics.data ?? []).filter((m) => m.available).map((m) => m.name)),
    [metrics.data],
  );
  // Until the user edits the checklist, use the recommended default set (restricted to available metrics).
  const chosenMetrics = selectedMetrics ?? DEFAULT_METRICS.filter((m) => availableMetricNames.has(m));

  const grouped = useMemo(() => {
    const g = new Map<string, MetricInfo[]>();
    for (const m of metrics.data ?? []) {
      const list = g.get(m.category) ?? [];
      list.push(m);
      g.set(m.category, list);
    }
    return [...g.entries()].sort((a, b) => categoryRank(a[0]) - categoryRank(b[0]));
  }, [metrics.data]);

  const dataset = datasets.data?.find((d) => d.id === datasetId);
  const cases = dataset ? Math.min(dataset.case_count, caseLimit ? Number(caseLimit) || dataset.case_count : dataset.case_count) : 0;
  const matrix = promptIds.length * modelIds.length * cases;

  const loading = datasets.isLoading || prompts.isLoading || models.isLoading || metrics.isLoading;
  const loadError = datasets.error ?? prompts.error ?? models.error ?? metrics.error;

  function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!name.trim()) return setFormError("Give the experiment a name.");
    if (!datasetId) return setFormError("Select a dataset.");
    if (!promptIds.length) return setFormError("Select at least one prompt version.");
    if (!modelIds.length) return setFormError("Select at least one model config.");
    if (!chosenMetrics.length) return setFormError("Select at least one metric.");
    const th: Record<string, number> = {};
    for (const t of thresholds) {
      if (!t.metric || t.value.trim() === "") continue;
      const n = Number(t.value);
      if (!Number.isFinite(n)) return setFormError(`Threshold for ${t.metric} must be a number.`);
      th[t.metric] = n;
    }
    create.mutate(
      {
        name: name.trim(),
        dataset_id: datasetId,
        prompt_version_ids: promptIds,
        model_config_ids: modelIds,
        metrics: chosenMetrics,
        thresholds: th,
        concurrency: concurrency ? Number(concurrency) : null,
        case_limit: caseLimit ? Number(caseLimit) : null,
      },
      { onSuccess: (exp) => navigate(`/experiments/${exp.id}`) },
    );
  }

  if (loading) {
    return (
      <div className="space-y-4 p-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-4">
        {loadError && <InlineError error={loadError} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" htmlFor="exp-name" required>
            <Input
              id="exp-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Support bot v3 vs v2"
              autoFocus
            />
          </Field>
          <Field label="Dataset" htmlFor="exp-dataset" required>
            <Select
              id="exp-dataset"
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              placeholder="Select a dataset"
              options={(datasets.data ?? []).map((d) => ({ value: d.id, label: `${d.name} (${d.case_count} cases)` }))}
            />
          </Field>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <section>
            <SectionTitle right={<span className="text-xs text-zinc-500">{promptIds.length} selected</span>}>
              Prompt versions
            </SectionTitle>
            <div className="max-h-56 space-y-3 overflow-y-auto rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
              {!prompts.data?.length && <p className="text-sm text-zinc-500">No prompt templates. Create one on the Prompts page.</p>}
              {prompts.data?.map((t) => (
                <div key={t.id}>
                  <div className="mb-1 text-xs font-medium text-zinc-700 dark:text-zinc-300">{t.name}</div>
                  <div className="space-y-1.5">
                    {t.versions.map((v) => (
                      <Checkbox
                        key={v.id}
                        checked={promptIds.includes(v.id)}
                        onChange={() => setPromptIds((l) => toggle(l, v.id))}
                        aria-label={`${t.name} v${v.version}`}
                        label={<span className="font-mono text-[12.5px]">v{v.version}</span>}
                        description={v.notes || undefined}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
          <section>
            <SectionTitle right={<span className="text-xs text-zinc-500">{modelIds.length} selected</span>}>
              Model configs
            </SectionTitle>
            <div className="max-h-56 space-y-1.5 overflow-y-auto rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
              {!models.data?.length && <p className="text-sm text-zinc-500">No model configs. Add one on the Models page.</p>}
              {models.data?.map((m) => (
                <Checkbox
                  key={m.id}
                  checked={modelIds.includes(m.id)}
                  onChange={() => setModelIds((l) => toggle(l, m.id))}
                  label={
                    <span className="flex flex-wrap items-center gap-1.5">
                      {m.name}
                      <Badge tone="neutral">{m.provider}</Badge>
                      {!m.available && <Badge tone="warning">not configured</Badge>}
                    </span>
                  }
                  description={
                    !m.available
                      ? "Provider credentials are missing; cases will error unless configured."
                      : `${m.model}, temp ${m.temperature ?? "default"}, max ${m.max_tokens} tokens`
                  }
                />
              ))}
            </div>
          </section>
        </div>

        <section>
          <SectionTitle
            right={
              <div className="flex gap-2">
                <button
                  type="button"
                  className="text-xs text-accent-600 hover:underline dark:text-accent-400"
                  onClick={() => setSelectedMetrics(DEFAULT_METRICS.filter((m) => availableMetricNames.has(m)))}
                >
                  Recommended
                </button>
                <button
                  type="button"
                  className="text-xs text-zinc-500 hover:underline"
                  onClick={() => setSelectedMetrics([])}
                >
                  Clear
                </button>
              </div>
            }
          >
            Metrics ({chosenMetrics.length})
          </SectionTitle>
          <div className="grid gap-4 rounded-md border border-zinc-200 p-3 sm:grid-cols-2 lg:grid-cols-3 dark:border-zinc-800">
            {grouped.map(([cat, list]) => (
              <div key={cat}>
                <div className="mb-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">{CATEGORY_LABEL[cat] ?? cat}</div>
                <div className="space-y-1.5">
                  {list.map((m) => (
                    <div key={m.name} title={m.description}>
                      <Checkbox
                        checked={chosenMetrics.includes(m.name)}
                        disabled={!m.available}
                        onChange={() => setSelectedMetrics(toggle(chosenMetrics, m.name))}
                        label={
                          <span className="font-mono text-[12.5px]">
                            {m.name}
                            {m.uses_llm && <span className="ml-1 font-sans text-[10px] text-accent-600 dark:text-accent-400">LLM</span>}
                          </span>
                        }
                        description={
                          !m.available
                            ? `requires the ${m.backend} extra`
                            : m.requires.length
                              ? `needs ${m.requires.join(", ")}`
                              : undefined
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionTitle
            right={
              <Button
                size="sm"
                variant="ghost"
                icon={<Plus className="size-3.5" />}
                onClick={() => setThresholds((t) => [...t, { key: Date.now(), metric: "", value: "" }])}
              >
                Add gate
              </Button>
            }
          >
            Quality gates (optional)
          </SectionTitle>
          {thresholds.length === 0 ? (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Gates fail the experiment when a metric mean crosses a threshold, e.g. faithfulness 0.8 (minimum) or latency_ms
              2500 (maximum; direction comes from the metric).
            </p>
          ) : (
            <div className="space-y-2">
              {thresholds.map((t, i) => (
                <div key={t.key} className="flex items-center gap-2">
                  <Select
                    aria-label={`Gate ${i + 1} metric`}
                    className="flex-1"
                    value={t.metric}
                    placeholder="Metric"
                    onChange={(e) =>
                      setThresholds((rows) => rows.map((r) => (r.key === t.key ? { ...r, metric: e.target.value } : r)))
                    }
                    options={chosenMetrics.map((m) => ({ value: m, label: m }))}
                  />
                  <Input
                    aria-label={`Gate ${i + 1} threshold`}
                    className="w-32"
                    type="number"
                    step="any"
                    placeholder="0.8"
                    value={t.value}
                    onChange={(e) =>
                      setThresholds((rows) => rows.map((r) => (r.key === t.key ? { ...r, value: e.target.value } : r)))
                    }
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Remove gate"
                    onClick={() => setThresholds((rows) => rows.filter((r) => r.key !== t.key))}
                    icon={<Trash2 className="size-3.5" />}
                  />
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Concurrency" htmlFor="exp-conc" hint="Parallel model calls. Leave empty for the server default.">
            <Input
              id="exp-conc"
              type="number"
              min={1}
              max={256}
              value={concurrency}
              onChange={(e) => setConcurrency(e.target.value)}
              placeholder="default"
            />
          </Field>
          <Field label="Case limit" htmlFor="exp-limit" hint="Only run the first N cases (useful for smoke tests).">
            <Input
              id="exp-limit"
              type="number"
              min={1}
              value={caseLimit}
              onChange={(e) => setCaseLimit(e.target.value)}
              placeholder="all cases"
            />
          </Field>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 px-5 py-3 dark:border-zinc-800">
        <div
          className={cn("flex items-center gap-2 text-sm", matrix ? "text-zinc-700 dark:text-zinc-300" : "text-zinc-400")}
          aria-live="polite"
        >
          <Grid3x3 className="size-4 text-accent-500" />
          <span className="tabular">
            {promptIds.length} prompts x {modelIds.length} models x {fmtInt(cases)} cases ={" "}
            <strong className="font-semibold">{fmtInt(matrix)}</strong> runs
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            Start experiment
          </Button>
        </div>
      </div>
      {(formError || create.error) && (
        <div className="px-5 pb-3">
          <InlineError error={formError ?? create.error} />
        </div>
      )}
    </form>
  );
}

export function NewExperimentModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New experiment"
      description="Evaluate every prompt version against every model on a dataset."
      className="max-w-4xl"
      bodyClassName="flex flex-col p-0 overflow-hidden"
    >
      {open && <Form onClose={onClose} />}
    </Modal>
  );
}
