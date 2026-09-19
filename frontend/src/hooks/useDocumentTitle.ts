import { useEffect } from "react";

export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    document.title = title ? `${title} - LLM Eval Platform` : "LLM Eval Platform";
  }, [title]);
}
