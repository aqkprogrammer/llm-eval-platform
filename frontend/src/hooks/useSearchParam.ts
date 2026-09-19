import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/** Read/write a set of URL query params; empty values are removed. */
export function useQueryParams<K extends string>() {
  const [params, setParams] = useSearchParams();
  const get = useCallback((k: K) => params.get(k) ?? "", [params]);
  const set = useCallback(
    (updates: Partial<Record<K, string | null | undefined>>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(updates) as [string, string | null | undefined][]) {
            if (v) next.set(k, v);
            else next.delete(k);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );
  return { get, set, params };
}
