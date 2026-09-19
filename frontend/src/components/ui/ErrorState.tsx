import { AlertTriangle, RotateCw } from "lucide-react";
import { cn } from "../../lib/cn";
import { Button } from "./Button";

export function ErrorState({
  error,
  title = "Something went wrong",
  onRetry,
  className,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  className?: string;
}) {
  const message = error instanceof Error ? error.message : String(error ?? "Unknown error");
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm dark:border-rose-900/50 dark:bg-rose-950/30",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rose-500" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-rose-800 dark:text-rose-300">{title}</p>
        <p className="mt-0.5 break-words text-rose-700/90 dark:text-rose-300/80">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="ghost" icon={<RotateCw className="size-3.5" />} onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p role="alert" className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
      {message}
    </p>
  );
}
