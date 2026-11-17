import { getApiUrl } from "../apiUrl.ts";
import { parseApiError, type ApiError, type ApiResult } from "../apiError.ts";

export function getStorageApiUrl(path: string): string {
  return getApiUrl(`/storage${path}`);
}

export async function storageRequest<T>(path: string, init?: { method?: string; body?: unknown }): Promise<ApiResult<T>> {
  try {
    const res = await fetch(getStorageApiUrl(path), {
      method: init?.method ?? (init?.body !== undefined ? "POST" : "GET"),
      headers: init?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      credentials: "include",
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

export function importJobsUrl(): string {
  return getApiUrl("/import-jobs");
}

export function encodeKey(key: string): string {
  return encodeURIComponent(key);
}
