import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../lib/cn";

const control =
  "w-full rounded-md border border-zinc-200 bg-white px-2.5 text-sm text-zinc-900 shadow-xs placeholder:text-zinc-400 " +
  "focus:border-accent-500 focus:ring-2 focus:ring-accent-500/25 focus:outline-none disabled:opacity-60 " +
  "dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500";

export function Field({
  label,
  hint,
  children,
  htmlFor,
  className,
  required,
}: {
  label: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
  required?: boolean;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-zinc-500 dark:text-zinc-400">{hint}</p>}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn(control, "h-8.5", className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { mono?: boolean }>(
  function Textarea({ className, mono, ...rest }, ref) {
    return <textarea ref={ref} className={cn(control, "py-2", mono && "font-mono text-[13px]", className)} {...rest} />;
  },
);

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export function Select({
  options,
  placeholder,
  className,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { options: SelectOption[]; placeholder?: string }) {
  return (
    <div className={cn("relative", className)}>
      <select className={cn(control, "h-8.5 appearance-none pr-8")} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-zinc-400"
        aria-hidden
      />
    </div>
  );
}

export function Checkbox({
  label,
  description,
  className,
  ...rest
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: ReactNode; description?: ReactNode }) {
  const id = useId();
  return (
    <label
      htmlFor={rest.id ?? id}
      className={cn(
        "flex cursor-pointer items-start gap-2 text-sm has-disabled:cursor-not-allowed has-disabled:opacity-50",
        className,
      )}
    >
      <input
        id={rest.id ?? id}
        type="checkbox"
        className="mt-0.5 size-3.5 shrink-0 rounded border-zinc-300 accent-accent-600 dark:border-zinc-700"
        {...rest}
      />
      <span className="min-w-0">
        <span className="block leading-5 text-zinc-800 dark:text-zinc-200">{label}</span>
        {description && <span className="block text-xs text-zinc-500 dark:text-zinc-400">{description}</span>}
      </span>
    </label>
  );
}
