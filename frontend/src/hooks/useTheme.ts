import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
const KEY = "theme";
const listeners = new Set<() => void>();

function readStored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

let current: Theme = readStored() ?? systemTheme();
document.documentElement.classList.toggle("dark", current === "dark");

function apply(t: Theme) {
  current = t;
  document.documentElement.classList.toggle("dark", t === "dark");
  listeners.forEach((l) => l());
}

window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
  if (!readStored()) apply(e.matches ? "dark" : "light");
});

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** Theme shared across the app: persisted in localStorage, defaults to prefers-color-scheme. */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, () => current);
  const setTheme = useCallback((t: Theme) => {
    try {
      localStorage.setItem(KEY, t);
    } catch {
      // storage unavailable: theme still applies for this session
    }
    apply(t);
  }, []);
  const toggle = useCallback(() => setTheme(current === "dark" ? "light" : "dark"), [setTheme]);
  return { theme, setTheme, toggle };
}
