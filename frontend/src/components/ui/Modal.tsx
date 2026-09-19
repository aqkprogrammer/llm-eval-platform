import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "../../lib/cn";

function useOverlay(open: boolean, onClose: () => void) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prev?.focus?.();
    };
  }, [open]);
}

function Header({
  id,
  title,
  description,
  onClose,
}: {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
      <div className="min-w-0">
        <h2 id={id} className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
          {title}
        </h2>
        {description && <div className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{description}</div>}
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 focus-visible:ring-2 focus-visible:ring-accent-500/60 focus-visible:outline-none dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Modal({ open, onClose, title, description, children, footer, className, bodyClassName }: OverlayProps) {
  useOverlay(open, onClose);
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (open) panel.current?.focus();
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8">
      <div className="animate-fade-in fixed inset-0 bg-zinc-950/50 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          "animate-modal-in relative my-auto flex max-h-[calc(100vh-4rem)] w-full max-w-2xl flex-col rounded-xl border border-zinc-200 bg-white shadow-2xl outline-none dark:border-zinc-800 dark:bg-zinc-950",
          className,
        )}
      >
        <Header id={titleId} title={title} description={description} onClose={onClose} />
        <div className={cn("min-h-0 flex-1 overflow-y-auto px-5 py-4", bodyClassName)}>{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2 border-t border-zinc-200 px-5 py-3 dark:border-zinc-800">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({ open, onClose, title, description, children, footer, className, bodyClassName }: OverlayProps) {
  useOverlay(open, onClose);
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (open) panel.current?.focus();
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div className="animate-fade-in fixed inset-0 bg-zinc-950/40" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          "animate-drawer-in fixed inset-y-0 right-0 flex w-full max-w-3xl flex-col border-l border-zinc-200 bg-white shadow-2xl outline-none dark:border-zinc-800 dark:bg-zinc-950",
          className,
        )}
      >
        <Header id={titleId} title={title} description={description} onClose={onClose} />
        <div className={cn("min-h-0 flex-1 overflow-y-auto px-5 py-4", bodyClassName)}>{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2 border-t border-zinc-200 px-5 py-3 dark:border-zinc-800">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
