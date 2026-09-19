import { useMemo } from "react";
import { cn } from "../../lib/cn";
import { lineDiff } from "../../lib/diff";

export function LineDiff({ before, after, label }: { before: string; after: string; label: string }) {
  const ops = useMemo(() => lineDiff(before, after), [before, after]);
  const added = ops.filter((o) => o.type === "add").length;
  const removed = ops.filter((o) => o.type === "del").length;
  return (
    <div className="overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-800">
      <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs dark:border-zinc-800 dark:bg-zinc-900/70">
        <span className="font-medium text-zinc-600 dark:text-zinc-300">{label}</span>
        <span className="tabular font-mono">
          <span className="text-emerald-600 dark:text-emerald-400">+{added}</span>{" "}
          <span className="text-rose-600 dark:text-rose-400">-{removed}</span>
        </span>
      </div>
      {added === 0 && removed === 0 ? (
        <p className="px-3 py-2 text-xs text-zinc-500 italic">No changes.</p>
      ) : (
        <div className="overflow-x-auto font-mono text-[12.5px] leading-relaxed">
          {ops.map((o, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                o.type === "add" && "bg-emerald-50 text-emerald-900 dark:bg-emerald-500/10 dark:text-emerald-200",
                o.type === "del" && "bg-rose-50 text-rose-900 dark:bg-rose-500/10 dark:text-rose-200",
                o.type === "same" && "text-zinc-600 dark:text-zinc-400",
              )}
            >
              <span className="tabular w-9 shrink-0 pr-2 text-right text-zinc-400 select-none">{o.a ?? ""}</span>
              <span className="tabular w-9 shrink-0 pr-2 text-right text-zinc-400 select-none">{o.b ?? ""}</span>
              <span className="w-4 shrink-0 text-center select-none" aria-hidden>
                {o.type === "add" ? "+" : o.type === "del" ? "-" : " "}
              </span>
              <span className="pr-3 whitespace-pre-wrap">{o.text || " "}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
