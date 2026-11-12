export interface ApiError {
  status: number;
  code: string;
  message: string;
  extra: Record<string, unknown>;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

function validationMessage(detail: unknown[]): string {
  return detail
    .map((item) => (item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string" ? (item as { msg: string }).msg : ""))
    .filter(Boolean)
    .join(" ; ");
}

export function parseApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (Array.isArray(detail)) return { status, code: "validation_error", message: validationMessage(detail), extra: { errors: detail } };
  if (detail && typeof detail === "object") {
    const { code, message, ...extra } = detail as Record<string, unknown>;
    return { status, code: typeof code === "string" ? code : "error", message: typeof message === "string" ? message : "", extra };
  }
  return { status, code: "error", message: typeof detail === "string" ? detail : "", extra: {} };
}

export function errorMessage(body: unknown, fallback: string): string {
  return parseApiError(0, body).message || fallback;
}
