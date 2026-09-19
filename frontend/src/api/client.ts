export const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildUrl(path: string, query?: Query): string {
  const url = `${API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationIssue[]).map((d) => {
      const loc = (d.loc ?? []).filter((p) => p !== "body").join(".");
      return loc ? `${loc}: ${d.msg ?? "invalid"}` : (d.msg ?? "invalid");
    });
    return parts.join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return null;
}

async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown } = {}): Promise<T> {
  const init: RequestInit = { method, headers: { Accept: "application/json" } };
  if (opts.body instanceof FormData) {
    init.body = opts.body;
  } else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers = { ...init.headers, "Content-Type": "application/json" };
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), init);
  } catch {
    throw new ApiError("Could not reach the API server. Is it running?", 0);
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`.trim();
    try {
      const data: unknown = await res.json();
      const detail = detailMessage((data as { detail?: unknown })?.detail);
      if (detail) message = detail;
    } catch {
      // non-JSON error body: keep status text
    }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
};
