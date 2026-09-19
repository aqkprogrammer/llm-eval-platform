import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Skeleton } from "./Skeleton";

export function StatCard({
  label,
  value,
  sub,
  icon,
  loading,
  tone,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  icon?: ReactNode;
  loading?: boolean;
  tone?: "danger" | "warning" | "success";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-zinc-200 bg-white p-4 shadow-xs dark:border-zinc-800/80 dark:bg-zinc-900/40",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-zinc-500 dark:text-zinc-400">
        <span className="truncate">{label}</span>
        {icon && <span className="text-zinc-400 dark:text-zinc-500">{icon}</span>}
      </div>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-20" />
      ) : (
        <div
          className={cn(
            "tabular mt-1.5 text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50",
            tone === "danger" && "text-rose-600 dark:text-rose-400",
            tone === "warning" && "text-amber-600 dark:text-amber-400",
            tone === "success" && "text-emerald-600 dark:text-emerald-400",
          )}
        >
          {value}
        </div>
      )}
      {sub && <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{sub}</div>}
    </div>
  );
}
