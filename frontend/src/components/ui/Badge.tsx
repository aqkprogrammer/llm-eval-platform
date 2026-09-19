import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

export type Tone = "neutral" | "success" | "danger" | "warning" | "info" | "accent";

const tones: Record<Tone, string> = {
  neutral: "bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800/60 dark:text-zinc-300 dark:ring-zinc-700/60",
  success:
    "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/25",
  danger: "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:ring-rose-500/25",
  warning: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/25",
  info: "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-400 dark:ring-sky-500/25",
  accent:
    "bg-accent-50 text-accent-700 ring-accent-200 dark:bg-accent-500/10 dark:text-accent-300 dark:ring-accent-500/25",
};

const dots: Record<Tone, string> = {
  neutral: "bg-zinc-400",
  success: "bg-emerald-500",
  danger: "bg-rose-500",
  warning: "bg-amber-500",
  info: "bg-sky-500",
  accent: "bg-accent-500",
};

export function Badge({
  tone = "neutral",
  dot,
  pulse,
  icon,
  className,
  children,
  title,
}: {
  tone?: Tone;
  dot?: boolean;
  pulse?: boolean;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[11px] leading-4 font-medium whitespace-nowrap ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {dot && (
        <span className="relative flex size-1.5">
          {pulse && <span className={cn("absolute inset-0 animate-ping rounded-full opacity-60", dots[tone])} />}
          <span className={cn("relative size-1.5 rounded-full", dots[tone])} />
        </span>
      )}
      {icon}
      {children}
    </span>
  );
}
