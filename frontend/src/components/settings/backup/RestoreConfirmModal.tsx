"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatBinarySize } from "@/lib/format";

export default function RestoreConfirmModal({ file, busy, onCancel, onConfirm }: {
  file: File; busy: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const { t } = useAppSettings();
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-text)" }}>
          <Icon name="upload" size={20} /> {t("settingsPage.restoreBackup")}
        </h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
          {t("settingsPage.restoreBackupConfirmText")}
        </p>
        <div style={{ padding: "10px 14px", background: "var(--bg-surface-hover)", borderRadius: "8px", fontSize: "0.85rem", border: "1px solid var(--border-color)" }}>
          <strong>{t("settingsPage.restoreBackupPrompt")}</strong>
          <div style={{ marginTop: "4px", fontFamily: "var(--font-mono, monospace)" }}>
            {file.name} ({formatBinarySize(file.size)})
          </div>
        </div>
        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={busy}
          >
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? t("settingsPage.restoringBackup") : t("settingsPage.restoreBackup")}
          </button>
        </div>
      </div>
    </div>
  );
}
