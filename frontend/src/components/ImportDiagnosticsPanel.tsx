"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { copyText } from "@/lib/clipboard";
import {
  formatAge,
  formatBytes,
  installHintKey,
  isBlockError,
  problemKeys,
  reportAsText,
  type DirectoryState,
  type ImportDiagnostics,
  type ToolState,
} from "@/lib/importDiagnostics";

function getApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") return `http://localhost:8001/api${path}`;
  return `/api${path}`;
}

type Row = { ok: boolean; label: string; value: string; hint?: string };

/**
 * Section « Diagnostic de l'import » de Réglages : ce dont l'import de médias a
 * besoin (ffmpeg/ffprobe, dossier temporaire, espace libre) et ce qui tourne en
 * ce moment. Un import qui ne progresse pas devient diagnostiquable en un coup
 * d'œil, et le rapport se copie pour une demande d'aide.
 */
export default function ImportDiagnosticsPanel() {
  const { t } = useAppSettings();
  const [report, setReport] = useState<ImportDiagnostics | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(getApiUrl("/diagnostics/import"), { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReport(await res.json());
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture ponctuelle d'une API externe au montage
    void load();
  }, [load]);

  const copy = async () => {
    if (!report) return;
    if (await copyText(reportAsText(report))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const blockError = (error: string) => t("settingsPage.importDiag.blockError", { error });
  const toolRow = (label: string, tool: ToolState | { error: string }, os: unknown): Row => {
    if (isBlockError(tool)) return { ok: false, label, value: blockError(tool.error) };
    if (!tool.found) return { ok: false, label, value: t("settingsPage.importDiag.missing"), hint: t(installHintKey(os)) };
    if (!tool.executable) return { ok: false, label, value: t("settingsPage.importDiag.notExecutable"), hint: tool.path };
    return { ok: !tool.error, label, value: t("settingsPage.importDiag.found", { path: tool.path }), hint: tool.version ?? tool.error ?? undefined };
  };
  const dirRow = (label: string, dir: DirectoryState | { error: string }): Row => {
    if (isBlockError(dir)) return { ok: false, label, value: blockError(dir.error) };
    const parts = [dir.writable ? t("settingsPage.importDiag.writable") : t("settingsPage.importDiag.notWritable"), t("settingsPage.importDiag.free", { size: formatBytes(dir.free_bytes) })];
    if (typeof dir.partial_uploads === "number" && dir.partial_uploads > 0) {
      parts.push(t("settingsPage.importDiag.partialUploads", { count: dir.partial_uploads, size: formatBytes(dir.partial_bytes) }));
    }
    return { ok: dir.exists && dir.writable, label, value: parts.join(" · "), hint: dir.error ? `${dir.path} — ${dir.error}` : dir.path };
  };

  const rows: Row[] = [];
  const problems = problemKeys(report?.problems);
  if (report) {
    rows.push(toolRow(t("settingsPage.importDiag.ffmpeg"), report.ffmpeg, report.os));
    rows.push(toolRow(t("settingsPage.importDiag.ffprobe"), report.ffprobe, report.os));
    rows.push(dirRow(t("settingsPage.importDiag.tempDir"), report.temp_dir));
    rows.push(dirRow(t("settingsPage.importDiag.stagingDir"), report.staging_dir));
    rows.push(dirRow(t("settingsPage.importDiag.mediaDir"), report.media_dir));
    const label = t("settingsPage.importDiag.executor");
    if (isBlockError(report.executors)) {
      rows.push({ ok: false, label, value: blockError(report.executors.error) });
    } else {
      const e = report.executors.ffmpeg;
      rows.push({
        ok: !e.shutdown,
        label,
        value: t("settingsPage.importDiag.executorValue", { alive: e.threads_alive, max: e.max_workers ?? "?", queued: e.queued ?? "?" }),
      });
    }
  }

  return (
    <section className="live-block" id="section-import-diagnostics">
      <h3><Icon name="troubleshoot" size={18} /> {t("settingsPage.importDiag.title")}</h3>
      <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.importDiag.hint")}</p>

      {failed && (
        <p role="alert" style={{ color: "var(--accent-error)", fontSize: "0.88rem" }}>{t("settingsPage.importDiag.loadError")}</p>
      )}

      {report && (
        <div data-testid="import-diagnostics">
          {problems.length === 0 ? (
            <p style={{ color: "var(--accent-success)", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}>
              <Icon name="check" size={16} color="var(--accent-success)" /> {t("settingsPage.importDiag.allGood")}
            </p>
          ) : (
            <ul role="alert" style={{ margin: "0 0 12px", paddingLeft: "18px", color: "var(--accent-warning)", fontSize: "0.88rem" }}>
              {problems.map((key) => <li key={key}>{t(key)}</li>)}
            </ul>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {rows.map((row) => (
              <div key={row.label} style={{ display: "flex", gap: "8px", alignItems: "flex-start", fontSize: "0.88rem" }}>
                <Icon name={row.ok ? "check" : "warning"} size={16} color={row.ok ? "var(--accent-success)" : "var(--accent-warning)"} />
                <div style={{ minWidth: 0 }}>
                  <strong style={{ color: "var(--text-main)" }}>{row.label}</strong>
                  <span style={{ color: "var(--text-muted)" }}> — {row.value}</span>
                  {row.hint && <div style={{ color: "var(--text-dim)", fontSize: "0.76rem", overflowWrap: "anywhere" }}>{row.hint}</div>}
                </div>
              </div>
            ))}
            <div style={{ fontSize: "0.88rem" }}>
              <strong style={{ color: "var(--text-main)" }}>{t("settingsPage.importDiag.jobs")}</strong>
              {isBlockError(report.jobs) ? (
                <span style={{ color: "var(--text-muted)" }}> — {blockError(report.jobs.error)}</span>
              ) : report.jobs.active.length === 0 ? (
                <span style={{ color: "var(--text-muted)" }}> — {t("settingsPage.importDiag.noJobs")}</span>
              ) : (
                <ul style={{ margin: "4px 0 0", paddingLeft: "18px", color: "var(--text-muted)" }}>
                  {report.jobs.active.map((job) => (
                    <li key={job.id}>
                      {t("settingsPage.importDiag.jobLine", {
                        kind: job.kind ?? "?", stage: job.stage, age: formatAge(job.age_seconds), idle: formatAge(job.idle_seconds),
                      })}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: "10px", marginTop: "14px", flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="btn btn-secondary" onClick={() => void load()} disabled={loading}>
          <Icon name="refresh" size={18} /> {loading ? t("settingsPage.importDiag.refreshing") : t("settingsPage.importDiag.refresh")}
        </button>
        {report && (
          <button type="button" className="btn btn-secondary" onClick={() => void copy()}>
            <Icon name="content_copy" size={18} /> {copied ? t("settingsPage.importDiag.copied") : t("settingsPage.importDiag.copy")}
          </button>
        )}
      </div>
    </section>
  );
}
