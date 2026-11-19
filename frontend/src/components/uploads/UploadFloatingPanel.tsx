"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useUploadManager } from "@/lib/UploadManager";
import UploadTaskRow from "./UploadTaskRow";

const PANEL_STYLE = {
  position: "fixed",
  bottom: "24px",
  right: "24px",
  zIndex: 9999,
  background: "var(--bg-surface-elevated)",
  border: "1px solid var(--border-color)",
  borderRadius: "12px",
  boxShadow: "0 8px 32px color-mix(in srgb, var(--ink) 40%, transparent)",
  overflow: "hidden",
  fontFamily: "var(--font-body)",
  fontSize: "0.85rem",
} as const;

const CLEAR_STYLE = {
  marginTop: "4px",
  alignSelf: "flex-end",
  background: "none",
  border: "none",
  color: "var(--text-muted)",
  cursor: "pointer",
  fontSize: "0.78rem",
  padding: "4px 0",
} as const;

function PanelHeader({ title, minimized, onToggle }: { title: string; minimized: boolean; onToggle: () => void }) {
  return (
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
      onClick={onToggle}
    >
      <span style={{ fontWeight: 700, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
        <Icon name="upload" size={16} />
        {title}
      </span>
      <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "flex", alignItems: "center" }}>
        <Icon name={minimized ? "expand_less" : "expand_more"} size={16} />
      </span>
    </div>
  );
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
    <div style={{ ...PANEL_STYLE, width: minimized ? "auto" : "420px" }}>
      <PanelHeader
        minimized={minimized}
        onToggle={() => setMinimized((m) => !m)}
        title={active.length > 0
          ? t(active.length > 1 ? "uploadManager.activeMany" : "uploadManager.activeOne", { count: active.length })
          : t(completed.length > 1 ? "uploadManager.doneMany" : "uploadManager.doneOne", { count: completed.length })}
      />
      {!minimized && (
        <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px", maxHeight: "320px", overflowY: "auto" }}>
          {uploads.map((task) => <UploadTaskRow key={task.id} t={t} task={task} onCancel={cancelUpload} />)}
          {completed.length > 0 && (
            <button onClick={clearCompleted} style={CLEAR_STYLE}>
              {t("uploadManager.clearDone")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
