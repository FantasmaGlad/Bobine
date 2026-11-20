import { formatBytes, installHintKey, isBlockError, type DirectoryState, type ImportDiagnostics, type ToolState } from "@/lib/importDiagnostics";

export type Row = { ok: boolean; label: string; value: string; hint?: string };
type T = (key: string, params?: Record<string, string | number>) => string;

export const blockErrorText = (error: string, t: T) => t("settingsPage.importDiag.blockError", { error });

function toolRow(label: string, tool: ToolState | { error: string }, os: unknown, t: T): Row {
  if (isBlockError(tool)) return { ok: false, label, value: blockErrorText(tool.error, t) };
  if (!tool.found) return { ok: false, label, value: t("settingsPage.importDiag.missing"), hint: t(installHintKey(os)) };
  if (!tool.executable) return { ok: false, label, value: t("settingsPage.importDiag.notExecutable"), hint: tool.path };
  return { ok: !tool.error, label, value: t("settingsPage.importDiag.found", { path: tool.path }), hint: tool.version ?? tool.error ?? undefined };
}

function dirRow(label: string, dir: DirectoryState | { error: string }, t: T): Row {
  if (isBlockError(dir)) return { ok: false, label, value: blockErrorText(dir.error, t) };
  const parts = [dir.writable ? t("settingsPage.importDiag.writable") : t("settingsPage.importDiag.notWritable"), t("settingsPage.importDiag.free", { size: formatBytes(dir.free_bytes) })];
  if (typeof dir.partial_uploads === "number" && dir.partial_uploads > 0) {
    parts.push(t("settingsPage.importDiag.partialUploads", { count: dir.partial_uploads, size: formatBytes(dir.partial_bytes) }));
  }
  return { ok: dir.exists && dir.writable, label, value: parts.join(" · "), hint: dir.error ? `${dir.path} — ${dir.error}` : dir.path };
}

function executorRow(report: ImportDiagnostics, t: T): Row {
  const label = t("settingsPage.importDiag.executor");
  if (isBlockError(report.executors)) return { ok: false, label, value: blockErrorText(report.executors.error, t) };
  const e = report.executors.ffmpeg;
  return {
    ok: !e.shutdown,
    label,
    value: t("settingsPage.importDiag.executorValue", { alive: e.threads_alive, max: e.max_workers ?? "?", queued: e.queued ?? "?" }),
  };
}

export function diagnosticsRows(report: ImportDiagnostics, t: T): Row[] {
  return [
    toolRow(t("settingsPage.importDiag.ffmpeg"), report.ffmpeg, report.os, t),
    toolRow(t("settingsPage.importDiag.ffprobe"), report.ffprobe, report.os, t),
    dirRow(t("settingsPage.importDiag.tempDir"), report.temp_dir, t),
    dirRow(t("settingsPage.importDiag.stagingDir"), report.staging_dir, t),
    dirRow(t("settingsPage.importDiag.mediaDir"), report.media_dir, t),
    executorRow(report, t),
  ];
}
