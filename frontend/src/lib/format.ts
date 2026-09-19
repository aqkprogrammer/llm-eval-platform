import type { MetricUnit } from "../api/types";

const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

export const DASH = "—";

const isNum = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

export function fmtNumber(v: number | null | undefined, digits = 0): string {
  if (!isNum(v)) return DASH;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(v);
}

export function fmtInt(v: number | null | undefined): string {
  return isNum(v) ? nf0.format(v) : DASH;
}

export function fmtScore(v: number | null | undefined, digits = 3): string {
  return isNum(v) ? v.toFixed(digits) : DASH;
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return DASH;
  return `${(v * 100).toFixed(digits).replace(/\.0+$/, "")}%`;
}

export function fmtMs(v: number | null | undefined): string {
  if (!isNum(v)) return DASH;
  if (v !== 0 && Math.abs(v) < 1) return `${v.toFixed(2)} ms`;
  if (Math.abs(v) < 10) return `${nf1.format(v)} ms`;
  return `${nf0.format(v)} ms`;
}

/** Compact duration for axes: ms, s, min or h depending on magnitude. */
export function fmtSpan(ms: number | null | undefined): string {
  if (!isNum(ms)) return DASH;
  const a = Math.abs(ms);
  if (a < 1000) return fmtMs(ms);
  if (a < 60_000) return `${nf1.format(ms / 1000)} s`;
  if (a < 3_600_000) return `${nf1.format(ms / 60_000)} min`;
  return `${nf1.format(ms / 3_600_000)} h`;
}

export function fmtUsd(v: number | null | undefined): string {
  if (!isNum(v)) return DASH;
  if (v === 0) return "$0";
  const abs = Math.abs(v);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 5;
  const s = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: digits,
  }).format(v);
  return s === "$0.00" || s === "-$0.00" ? `<$0.00001` : s;
}

export function fmtTokens(v: number | null | undefined): string {
  return isNum(v) ? nf0.format(Math.round(v)) : DASH;
}

/** Format a metric value according to its unit. */
export function fmtMetric(v: number | null | undefined, unit: MetricUnit | string | undefined): string {
  switch (unit) {
    case "ms":
      return fmtMs(v);
    case "usd":
      return fmtUsd(v);
    case "tokens":
      return fmtTokens(v);
    case "count":
      return fmtNumber(v, 2);
    default:
      return fmtScore(v);
  }
}

/** Signed delta, formatted by unit. */
export function fmtDelta(v: number | null | undefined, unit: MetricUnit | string | undefined): string {
  if (!isNum(v)) return DASH;
  const sign = v > 0 ? "+" : v < 0 ? "-" : "±";
  return `${sign}${fmtMetric(Math.abs(v), unit)}`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return DASH;
  const diff = (Date.now() - t) / 1000;
  const abs = Math.abs(diff);
  const suffix = diff >= 0 ? "ago" : "from now";
  if (abs < 45) return "just now";
  if (abs < 3600) return `${Math.round(abs / 60)} min ${suffix}`;
  if (abs < 86400) return `${Math.round(abs / 3600)} h ${suffix}`;
  if (abs < 86400 * 30) return `${Math.round(abs / 86400)} d ${suffix}`;
  return fmtDate(iso);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function fmtDuration(startIso: string | null | undefined, endIso: string | null | undefined): string {
  if (!startIso || !endIso) return DASH;
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (ms < 1000) return `${Math.max(0, ms)} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)} s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function truncate(s: string | null | undefined, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : DASH;
}

export function humanize(name: string): string {
  return name.replace(/_/g, " ").replace(/\bms\b/, "(ms)").replace(/\busd\b/, "(USD)");
}
