import type { ReactNode } from "react";

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  );
}

export function TextPanel({ children, tone }: { children: ReactNode; tone?: "danger" }) {
  return (
    <div
      className={
        tone === "danger"
          ? "rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm whitespace-pre-wrap text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300"
          : "rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm whitespace-pre-wrap text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-200"
      }
    >
      {children}
    </div>
  );
}

export function StatsRow({ items }: { items: { label: string; value: string }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-zinc-200 bg-zinc-200 sm:grid-cols-4 dark:border-zinc-800 dark:bg-zinc-800">
      {items.map((it) => (
        <div key={it.label} className="bg-white px-3 py-2 dark:bg-zinc-950">
          <dt className="text-[11px] text-zinc-500 dark:text-zinc-400">{it.label}</dt>
          <dd className="tabular mt-0.5 font-mono text-sm font-medium text-zinc-900 dark:text-zinc-100">{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ContextList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-sm text-zinc-500 italic dark:text-zinc-400">No context provided.</p>;
  return (
    <ol className="space-y-1.5">
      {items.map((c, i) => (
        <li key={i} className="flex gap-2 rounded-md border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
          <span className="tabular shrink-0 font-mono text-xs text-zinc-400">[{i + 1}]</span>
          <span className="text-zinc-700 dark:text-zinc-300">{c}</span>
        </li>
      ))}
    </ol>
  );
}
