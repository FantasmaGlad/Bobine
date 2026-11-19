"use client";

import React from "react";
import Icon from "@/components/Icon";
import type { useUploadManager } from "@/lib/UploadManager";
import { formatNotice } from "@/lib/uploadFlow";
import UploadTaskBars from "./UploadTaskBars";
import UploadTaskDetail from "./UploadTaskDetail";
import { formatEta, STAGE_ICONS } from "./uploadText";

type Task = ReturnType<typeof useUploadManager>["uploads"][number];
type Translate = (key: string, vars?: Record<string, string | number>) => string;

const CANCEL_STYLE = {
  background: "none",
  border: "none",
  color: "var(--text-muted)",
  cursor: "pointer",
  padding: "2px 4px",
  fontSize: "0.9rem",
  lineHeight: 1,
  display: "flex",
  alignItems: "center",
} as const;

function TaskTitle({ task }: { task: Task }) {
  return (
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
  );
}

export default function UploadTaskRow({ t, task, onCancel }: { t: Translate; task: Task; onCancel: (id: string) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <TaskTitle task={task} />
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, whiteSpace: "nowrap" }}>
          {task.status === "uploading" && (
            <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
              {task.progress}%{task.uploadEtaSeconds ? ` (${formatEta(task.uploadEtaSeconds)})` : ""}
            </span>
          )}
          {(task.status === "uploading" || task.status === "pending" || task.status === "processing") && (
            <button
              onClick={() => onCancel(task.id)}
              title={t("uploadManager.cancelImport")}
              style={CANCEL_STYLE}
            >
              <Icon name="close" size={14} />
            </button>
          )}
        </div>
      </div>
      <UploadTaskDetail t={t} task={task} />
      <UploadTaskBars task={task} />
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
  );
}
