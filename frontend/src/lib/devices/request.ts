import type { ApiResult } from "../apiError.ts";
import { requestJson } from "../apiRequest.ts";
import { getApiUrl } from "../apiUrl.ts";

export function getDevicesApiUrl(path: string): string {
  return getApiUrl(`/devices${path}`);
}

export function devicesRequest<T>(path: string, init?: { method?: string; body?: unknown }): Promise<ApiResult<T>> {
  return requestJson<T>(getDevicesApiUrl(path), init);
}
