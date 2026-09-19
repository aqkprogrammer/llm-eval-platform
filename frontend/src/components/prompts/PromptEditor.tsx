import { useMemo, useState, type FormEvent } from "react";
import { Eye } from "lucide-react";
import { usePromptPreview } from "../../api/queries";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { CodeBlock } from "../ui/CodeBlock";
import { InlineError } from "../ui/ErrorState";
import { Field, Input, Textarea } from "../ui/Field";

export interface PromptDraft {
  name?: string;
  description?: string;
  system_prompt: string;
  user_template: string;
  notes: string;
}

const SAMPLE_CONTEXT =
  "Acme accepts returns within 30 days of delivery. Items must be unused and in their original packaging.\n\nRefunds are issued within 5 business days after the return is received.";

/** Shared form for new templates and new versions, with a live server-side render preview. */
export function PromptEditor({
  initial,
  withName,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: PromptDraft;
  withName?: boolean;
  submitLabel: string;
  pending: boolean;
  error: unknown;
  onSubmit: (d: PromptDraft) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<PromptDraft>(initial);
  const [sampleInput, setSampleInput] = useState("How long do I have to return an item?");
  const [sampleContext, setSampleContext] = useState(SAMPLE_CONTEXT);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const set = (k: keyof PromptDraft) => (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [k]: e.target.value }));

  const req = useMemo(
    () => ({
      system_prompt: draft.system_prompt,
      user_template: draft.user_template,
      input: sampleInput,
      context: sampleContext
        .split(/\n\s*\n/)
        .map((s) => s.trim())
        .filter(Boolean),
    }),
    [draft.system_prompt, draft.user_template, sampleInput, sampleContext],
  );
  const previewReq = useDebouncedValue(req, 350);
  const preview = usePromptPreview(previewReq);

  function submit(e: FormEvent) {
    e.preventDefault();
    setLocalErr(null);
    if (withName && !draft.name?.trim()) return setLocalErr("Name is required.");
    if (!draft.user_template.trim()) return setLocalErr("User template is required.");
    onSubmit({ ...draft, name: draft.name?.trim() });
  }

  return (
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        {withName && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" htmlFor="pt-name" required>
              <Input id="pt-name" value={draft.name ?? ""} onChange={set("name")} placeholder="support-assistant" autoFocus />
            </Field>
            <Field label="Description" htmlFor="pt-desc">
              <Input id="pt-desc" value={draft.description ?? ""} onChange={set("description")} />
            </Field>
          </div>
        )}
        <Field label="System prompt" htmlFor="pt-system">
          <Textarea id="pt-system" mono rows={4} value={draft.system_prompt} onChange={set("system_prompt")} />
        </Field>
        <Field
          label="User template"
          htmlFor="pt-user"
          required
          hint={
            <>
              Jinja-style variables: <code className="font-mono">{"{{ input }}"}</code>,{" "}
              <code className="font-mono">{"{{ context_str }}"}</code>, <code className="font-mono">{"{{ context }}"}</code> and
              metadata keys.
            </>
          }
        >
          <Textarea id="pt-user" mono rows={8} value={draft.user_template} onChange={set("user_template")} />
        </Field>
        <Field label="Notes" htmlFor="pt-notes" hint="What changed and why (shown in the version list).">
          <Input id="pt-notes" value={draft.notes} onChange={set("notes")} placeholder="Tighter grounding instructions" />
        </Field>
        {localErr || error ? <InlineError error={localErr ?? error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={pending}>
            {submitLabel}
          </Button>
        </div>
      </div>

      <div className="space-y-4 rounded-lg border border-zinc-200 bg-zinc-50/60 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-800 dark:text-zinc-200">
          <Eye className="size-4 text-accent-500" /> Live preview
        </div>
        <Field label="Sample input" htmlFor="pv-input">
          <Input id="pv-input" value={sampleInput} onChange={(e) => setSampleInput(e.target.value)} />
        </Field>
        <Field label="Sample context" htmlFor="pv-ctx" hint="Separate passages with a blank line.">
          <Textarea id="pv-ctx" rows={3} value={sampleContext} onChange={(e) => setSampleContext(e.target.value)} />
        </Field>
        {preview.error ? (
          <InlineError error={preview.error} />
        ) : preview.data ? (
          <div className="space-y-3">
            {preview.data.variables.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 text-xs text-zinc-500">
                Variables:
                {preview.data.variables.map((v) => (
                  <Badge key={v} tone="accent">
                    {v}
                  </Badge>
                ))}
              </div>
            )}
            {preview.data.system && <CodeBlock label="System">{preview.data.system}</CodeBlock>}
            <CodeBlock label="User">{preview.data.user}</CodeBlock>
          </div>
        ) : (
          <p className="text-xs text-zinc-500">Type a user template to see the rendered prompt.</p>
        )}
      </div>
    </form>
  );
}
