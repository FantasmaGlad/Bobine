"use client";
import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { ShowToast } from "@/lib/useToast";
import RestoreConfirmModal from "./backup/RestoreConfirmModal";
import { useBackup } from "./backup/useBackup";

export default function BackupSection({ hidden, showToast }: { hidden: boolean; showToast: ShowToast }) {
  const { t } = useAppSettings();
  const { exportingBackup, restoringBackup, showRestoreConfirm, selectedBackupFile,
    handleExportBackup, handleSelectBackupFile, handleRestoreBackup, cancelRestore } = useBackup(showToast);

  return (
    <>
      <section className="live-block" id="section-backup" hidden={hidden}>
        <h3><Icon name="archive" size={18} /> {t("settingsPage.backupSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.backupHint")}</p>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "44px", display: "inline-flex", alignItems: "center", gap: "8px" }}
            onClick={handleExportBackup}
            disabled={exportingBackup}
          >
            <Icon name="download" size={16} />
            {exportingBackup ? t("settingsPage.exportingBackup") : t("settingsPage.exportBackup")}
          </button>

          <label
            className="btn btn-secondary"
            style={{ minHeight: "44px", display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer", margin: 0 }}
          >
            <Icon name="upload" size={16} />
            {t("settingsPage.restoreBackup")}
            <input
              type="file"
              accept=".zip"
              style={{ display: "none" }}
              onChange={handleSelectBackupFile}
            />
          </label>
        </div>
      </section>
      {showRestoreConfirm && selectedBackupFile && (
        <RestoreConfirmModal file={selectedBackupFile} busy={restoringBackup} onCancel={cancelRestore} onConfirm={handleRestoreBackup} />
      )}
    </>
  );
}
