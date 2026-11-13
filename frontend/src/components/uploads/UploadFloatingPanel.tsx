"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useUploadManager, type UploadKind } from "@/lib/UploadManager";
import { formatNotice, phaseLabelKey } from "@/lib/uploadFlow";

const STAGE_ICONS: Record<string, string> = {
  queued: "hourglass_empty",
  probing: "search",
  normalizing: "autorenew",
  copying: "drive_file_move",
  thumbnail: "image",
  extracting: "folder_zip",
  saving: "save",
};

const KIND_LABEL_KEYS: Record<UploadKind, string> = {
  video: "uploadManager.kindVideo",
  background: "uploadManager.kindBackground",
  video_zip: "uploadManager.kindVideo",
  background_zip: "uploadManager.kindBackground",
  audio_files: "uploadManager.kindAudio",
  audio_zip: "uploadManager.kindAudio",
  radio_files: "uploadManager.kindRadio",
  radio_zip: "uploadManager.kindRadio",
  radio_announcement_files: "uploadManager.kindAnnouncements",
};

function formatEta(seconds: number | null | undefined): string | null {
  if (typeof seconds !== "number" || isNaN(seconds) || seconds < 0) return null;
  if (seconds < 60) return `~${seconds}s restantes`;
  const mins = Math.floor(seconds / 60);
  const remSecs = seconds % 60;
  return remSecs > 0 ? `~${mins} min ${remSecs}s restantes` : `~${mins} min restantes`;
}

function formatQueueSuffix(queuePosition: number | null | undefined, queueEtaSeconds: number | null | undefined): string {
  if (typeof queuePosition !== "number" || queuePosition <= 0) return "";
  const eta = formatEta(queueEtaSeconds);
  const etaSuffix = eta ? `, ${eta.replace("restantes", "au total")}` : "";
  return ` (${queuePosition} devant${etaSuffix})`;
}

export default function UploadFloatingPanel() {
  const { uploads, cancelUpload, clearCompleted } = useUploadManager();
  const { t } = useAppSettings();
  const [minimized, setMinimized] = useState(false);

  const visible = uploads.length > 0;
  if (!visible) return null;

  const active = uploads.filter((u) => u.status === "uploading" || u.status === "pending" || u.status === "processing");
  const completed = uploads.filter((u) => u.status === "done" || u.status === "error");

  return (
    <div
      style={{
        position: "fixed",
        bottom: "24px",
        right: "24px",
        zIndex: 9999,
        width: minimized ? "auto" : "420px",
        background: "var(--bg-surface-elevated)",
        border: "1px solid var(--border-color)",
        borderRadius: "12px",
        boxShadow: "0 8px 32px color-mix(in srgb, var(--ink) 40%, transparent)",
        overflow: "hidden",
        fontFamily: "var(--font-body)",
        fontSize: "0.85rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          background: "var(--bg-surface-hover)",
          borderBottom: minimized ? "none" : "1px solid var(--border-color)",
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setMinimized((m) => !m)}
      >
        <span style={{ fontWeight: 700, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
          <Icon name="upload" size={16} />
          {active.length > 0
            ? t(active.length > 1 ? "uploadManager.activeMany" : "uploadManager.activeOne", { count: active.length })
            : t(completed.length > 1 ? "uploadManager.doneMany" : "uploadManager.doneOne", { count: completed.length })}
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "flex", alignItems: "center" }}>
          <Icon name={minimized ? "expand_less" : "expand_more"} size={16} />
        </span>
      </div>

      {!minimized && (
        <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px", maxHeight: "320px", overflowY: "auto" }}>
          {uploads.map((task) => (
            <div key={task.id} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span
                  style={{
                    color: task.status === "error" ? "var(--accent-error-text)" : task.status === "done" ? "var(--accent-success-text)" : "var(--text-main)",
                    fontWeight: 600,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: "230px",
                    flexShrink: 1,
                    minWidth: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                  title={task.title}
                >
                  {task.status === "done" && <Icon name="check" size={14} color="var(--accent-success-text)" />}
                  {task.status === "error" && <Icon name="close" size={14} color="var(--accent-error-text)" />}
                  {task.status === "pending" && <Icon name="hourglass_empty" size={14} />}
                  {task.status === "processing" && (
                    <Icon name={STAGE_ICONS[task.stage ?? ""] ?? "autorenew"} size={14} className="olc-spin" />
                  )}
                  {task.title}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, whiteSpace: "nowrap" }}>
                  {task.status === "uploading" && (
                    <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      {task.progress}%{task.uploadEtaSeconds ? ` (${formatEta(task.uploadEtaSeconds)})` : ""}
                    </span>
                  )}
                  {(task.status === "uploading" || task.status === "pending" || task.status === "processing") && (
                    <button
                      onClick={() => cancelUpload(task.id)}
                      title={t("uploadManager.cancelImport")}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        padding: "2px 4px",
                        fontSize: "0.9rem",
                        lineHeight: 1,
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      <Icon name="close" size={14} />
                    </button>
                  )}
                </div>
              </div>
              <span style={{ color: "var(--text-dim)", fontSize: "0.72rem" }}>
                {t(KIND_LABEL_KEYS[task.kind])}
                {task.status === "uploading" && (
                  <>{" — "}{t(phaseLabelKey(task.phase ?? "sending"))}</>
                )}
                {task.status === "processing" && (
                  <>
                    {" — "}
                    {t(phaseLabelKey("processing"))}{" : "}
                    {task.stage === "normalizing" && typeof task.progressPercent === "number" ? (
                      <>
                        {t("uploadManager.reencoding", { percent: task.progressPercent })}
                        {typeof task.etaSeconds === "number" ? (
                          ` — ${formatEta(task.etaSeconds)}`
                        ) : typeof task.estimatedSeconds === "number" ? (
                          ` — ${formatEta(task.estimatedSeconds)} (estimation)`
                        ) : null}
                        {task.speed && ` (${task.speed})`}
                      </>
                    ) : (
                      <>
                        {task.stageLabel ?? "Traitement…"}
                        {task.stage === "normalizing" && typeof task.estimatedSeconds === "number" &&
                          ` — ${formatEta(task.estimatedSeconds)} (estimation)`}
                      </>
                    )}
                    {formatQueueSuffix(task.queuePosition, task.queueEtaSeconds)}
                  </>
                )}
              </span>
              {task.status === "uploading" && (
                <div style={{ height: "3px", background: "var(--border-color)", borderRadius: "2px" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${task.progress}%`,
                      background: "var(--accent-primary)",
                      borderRadius: "2px",
                      transition: "width 0.2s",
                    }}
                  />
                </div>
              )}
              {task.status === "processing" && (
                <div style={{ height: "3px", background: "var(--border-color)", borderRadius: "2px", overflow: "hidden" }}>
                  {task.stage === "normalizing" && typeof task.progressPercent === "number" ? (
                    <div
                      style={{
                        height: "100%",
                        width: `${task.progressPercent}%`,
                        background: "var(--accent-primary)",
                        borderRadius: "2px",
                        transition: "width 0.4s",
                      }}
                    />
                  ) : (
                    <div className="olc-indeterminate-bar" style={{ background: "var(--accent-primary)" }} />
                  )}
                </div>
              )}
              {task.notice && (task.status === "uploading" || task.status === "processing") && (
                <span role="status" data-testid="upload-notice" style={{ color: "var(--accent-warning-text)", fontSize: "0.75rem" }}>
                  {formatNotice(t, task.notice)}
                </span>
              )}
              {task.status === "error" && task.error && (
                <span role="alert" style={{ color: "var(--accent-error-text)", fontSize: "0.78rem" }}>
                  {task.errorNotice ? formatNotice(t, task.errorNotice) : task.error}
                </span>
              )}
            </div>
          ))}

          {completed.length > 0 && (
            <button
              onClick={clearCompleted}
              style={{
                marginTop: "4px",
                alignSelf: "flex-end",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                fontSize: "0.78rem",
                padding: "4px 0",
              }}
            >
              {t("uploadManager.clearDone")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
