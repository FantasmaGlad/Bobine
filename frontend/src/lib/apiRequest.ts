import { parseApiError, type ApiError, type ApiResult } from "./apiError.ts";

export interface JsonRequest {
  method?: string;
  body?: unknown;
  credentials?: RequestCredentials;
}

export async function requestJson<T>(url: string, init?: JsonRequest): Promise<ApiResult<T>> {
  try {
    const res = await fetch(url, {
      method: init?.method ?? (init?.body !== undefined ? "POST" : "GET"),
      headers: init?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      credentials: init?.credentials,
      cache: "no-store",
    });
    const text = await res.text();
    let json: unknown = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    if (!res.ok) return { ok: false, error: parseApiError(res.status, json) };
    return { ok: true, data: json as T };
  } catch {
    return { ok: false, error: { status: 0, code: "network", message: "", extra: {} } as ApiError };
  }
}
