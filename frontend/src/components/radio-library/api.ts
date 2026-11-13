import { getApiUrl } from "@/lib/apiUrl";

export async function fetchJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(getApiUrl(path), { cache: "no-store" });
    return res.ok ? await res.json() : fallback;
  } catch {
    return fallback;
  }
}

export function sendJson(path: string, method: string, body?: unknown): Promise<Response> {
  return fetch(getApiUrl(path), {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function parseIntOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const n = parseInt(trimmed, 10);
  return Number.isNaN(n) ? null : n;
}
