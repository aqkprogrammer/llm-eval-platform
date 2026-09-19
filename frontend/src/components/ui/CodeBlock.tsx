import { useState, type ReactNode } from "react";
import { Check, ChevronRight, Copy } from "lucide-react";
import { cn } from "../../lib/cn";

export function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label="Copy to clipboard"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className={cn(
        "rounded p-1 text-zinc-400 hover:bg-zinc-200/70 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200",
        className,
      )}
    >
      {copied ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
    </button>
  );
}

export function CodeBlock({
  children,
  className,
  copy = true,
  label,
}: {
  children: string;
  className?: string;
  copy?: boolean;
  label?: string;
}) {
  return (
    <div
      className={cn(
        "group relative rounded-md border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/70",
        className,
      )}
    >
      {label && (
        <div className="border-b border-zinc-200 px-3 py-1.5 text-[11px] font-medium tracking-wide text-zinc-500 uppercase dark:border-zinc-800 dark:text-zinc-400">
          {label}
        </div>
      )}
      <pre className="overflow-x-auto px-3 py-2.5 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap break-words text-zinc-800 dark:text-zinc-200">
        {children || <span className="text-zinc-400 italic">(empty)</span>}
      </pre>
      {copy && children && (
        <CopyButton text={children} className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 focus:opacity-100" />
      )}
    </div>
  );
}

export function JsonView({ value, className }: { value: unknown; className?: string }) {
  return <CodeBlock className={className}>{JSON.stringify(value, null, 2)}</CodeBlock>;
}

export function Collapsible({
  title,
  children,
  defaultOpen = false,
  right,
}: {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  right?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="inline-flex items-center gap-1 text-xs font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
          {title}
        </button>
        {right}
      </div>
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}
