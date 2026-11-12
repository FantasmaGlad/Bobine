export type UploadPhase = "connecting" | "sending" | "processing";

export interface UploadNotice {
  key: string;
  params?: Record<string, string | number>;
}

export const JOB_MISS_LIMIT = 4;

export const POLL_FAILURE_LIMIT = 3;

export function nextMissCount(previous: number | undefined, found: boolean): number {
  return found ? 0 : (previous ?? 0) + 1;
}

export function isJobLost(misses: number, limit: number = JOB_MISS_LIMIT): boolean {
  return misses >= limit;
}

export function nextPollFailures(previous: number, ok: boolean): number {
  return ok ? 0 : previous + 1;
}

export function isServerSilent(failures: number, limit: number = POLL_FAILURE_LIMIT): boolean {
  return failures >= limit;
}

export function phaseLabelKey(phase: UploadPhase): string {
  return `uploads.phase.${phase}`;
}

export type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

export function formatNotice(t: TranslateFn, notice: UploadNotice): string {
  const params: Record<string, string | number> = { ...(notice.params ?? {}) };
  for (const name of Object.keys(params)) {
    const value = params[name];
    if (name.endsWith("Key") && typeof value === "string") {
      params[name.slice(0, -3)] = t(value, params);
      delete params[name];
    }
  }
  return t(notice.key, params);
}

export function jobErrorNotice(code: string | null | undefined, params: Record<string, unknown> | null | undefined): UploadNotice | undefined {
  if (code === "media_tool_missing") {
    const tool = typeof params?.tool === "string" ? params.tool : "ffmpeg";
    const os = typeof params?.os === "string" && ["macos", "windows", "linux", "android"].includes(params.os) ? params.os : "linux";
    return { key: "uploads.errors.mediaToolMissing", params: { tool, hintKey: `uploads.errors.installHint.${os}` } };
  }
  return undefined;
}

export function retryNotice(attempt: number, max: number, reasonKey: string, status?: number): UploadNotice {
  if (reasonKey === "uploads.reason.server") {
    return { key: "uploads.retryingServerError", params: { attempt, max, status: status ?? 0 } };
  }
  return { key: "uploads.retrying", params: { attempt, max } };
}

export function backoffMs(failures: number): number {
  return Math.min(15000, 1000 * 2 ** (Math.max(1, failures) - 1));
}
