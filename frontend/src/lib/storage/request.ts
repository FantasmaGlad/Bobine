import { getApiUrl } from "../apiUrl.ts";
import type { ApiResult } from "../apiError.ts";
import { requestJson } from "../apiRequest.ts";

export function getStorageApiUrl(path: string): string {
  return getApiUrl(`/storage${path}`);
}

export function storageRequest<T>(path: string, init?: { method?: string; body?: unknown }): Promise<ApiResult<T>> {
  return requestJson<T>(getStorageApiUrl(path), { ...init, credentials: "include" });
}

export function importJobsUrl(): string {
  return getApiUrl("/import-jobs");
}

export function encodeKey(key: string): string {
  return encodeURIComponent(key);
}
