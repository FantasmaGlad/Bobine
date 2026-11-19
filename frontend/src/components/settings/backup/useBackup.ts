"use client";

import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

export function useBackup(showToast: ShowToast) {
  const { t } = useAppSettings();
  const [exportingBackup, setExportingBackup] = useState(false);
  const [restoringBackup, setRestoringBackup] = useState(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const [selectedBackupFile, setSelectedBackupFile] = useState<File | null>(null);
  const handleExportBackup = () => {
    setExportingBackup(true);
    const url = getApiUrl("/settings/backup/export");
    const a = document.createElement("a");
    a.href = url;
    a.download = `bobine-backup-${new Date().toISOString().slice(0, 10)}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => setExportingBackup(false), 2000);
  };

  const handleSelectBackupFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedBackupFile(file);
      setShowRestoreConfirm(true);
    }
    e.target.value = "";
  };

  const handleRestoreBackup = async () => {
    if (!selectedBackupFile) return;
    setRestoringBackup(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedBackupFile);
      const res = await fetch(getApiUrl("/settings/backup/restore"), {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        showToast(t("settingsPage.restoreSuccess"), "success");
        setShowRestoreConfirm(false);
        setSelectedBackupFile(null);
      } else {
        const err = await res.json().catch(() => null);
        showToast(errorMessage(err, t("settingsPage.restoreError")), "error");
      }
    } catch {
      showToast(t("settingsPage.restoreError"), "error");
    } finally {
      setRestoringBackup(false);
    }
  };

  const cancelRestore = () => { setShowRestoreConfirm(false); setSelectedBackupFile(null); };
  return {
    exportingBackup, restoringBackup, showRestoreConfirm, selectedBackupFile,
    handleExportBackup, handleSelectBackupFile, handleRestoreBackup, cancelRestore,
  };
}
