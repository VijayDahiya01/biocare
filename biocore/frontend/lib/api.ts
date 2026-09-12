// Thin API client for the BioCore backend.
//
// Auth is cookie-based (HttpOnly session). We never store tokens in JS. For
// mutating requests we echo the readable `csrf` cookie in the X-CSRF-Token
// header, matching the backend's CSRF check.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
}

type Options = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method || "GET";
  const headers: Record<string, string> = { ...opts.headers };

  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = readCookie("csrf");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  let json: any = null;
  try {
    json = await res.json();
  } catch {
    /* empty / non-json */
  }

  if (!res.ok || (json && json.success === false)) {
    const err = json?.error ?? {};
    throw new ApiError(res.status, err.code || "ERROR", err.message || res.statusText, err.details);
  }
  return (json?.data ?? json) as T;
}

// Multipart upload (e.g. CSV import). Sends the CSRF header; lets the browser
// set the multipart boundary itself.
export async function apiUpload<T = any>(path: string, formData: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const csrf = readCookie("csrf");
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const res = await fetch(`${BASE}${path}`, {
    method: "POST", headers, credentials: "include", body: formData,
  });
  const json = await res.json().catch(() => null);
  if (!res.ok || (json && json.success === false)) {
    const err = json?.error ?? {};
    throw new ApiError(res.status, err.code || "ERROR", err.message || res.statusText);
  }
  return (json?.data ?? json) as T;
}

// Download a file response (CSV exports) with the session cookie attached.
export async function apiDownload(path: string, filename: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    const json = await res.json().catch(() => null);
    const err = json?.error ?? {};
    throw new ApiError(res.status, err.code || "ERROR", err.message || res.statusText);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Kiosk calls authenticate by device token (header), not a session cookie.
export async function deviceGet(path: string, deviceToken: string) {
  const res = await fetch(`${BASE}${path}`, { headers: { "X-Device-Token": deviceToken } });
  const json = await res.json().catch(() => null);
  if (!res.ok || (json && json.success === false)) {
    const err = json?.error ?? {};
    throw new ApiError(res.status, err.code || "ERROR", err.message || res.statusText);
  }
  return json.data;
}

export async function deviceSearch(path: string, deviceToken: string, body: unknown) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Device-Token": deviceToken },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => null);
  if (!res.ok || (json && json.success === false)) {
    const err = json?.error ?? {};
    throw new ApiError(res.status, err.code || "ERROR", err.message || res.statusText);
  }
  return json.data;
}
