import { ChevronLeft, ChevronRight } from "lucide-react";
import { fmtInt } from "../../lib/format";
import { Button } from "./Button";

export function Pagination({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <div className="flex items-center justify-between gap-3 border-t border-zinc-100 px-4 py-2.5 text-xs text-zinc-500 dark:border-zinc-800/70 dark:text-zinc-400">
      <span className="tabular">
        {fmtInt(from)}-{fmtInt(to)} of {fmtInt(total)}
      </span>
      <div className="flex gap-1">
        <Button
          size="sm"
          variant="ghost"
          aria-label="Previous page"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          icon={<ChevronLeft className="size-3.5" />}
        >
          Prev
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Next page"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
          <ChevronRight className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
