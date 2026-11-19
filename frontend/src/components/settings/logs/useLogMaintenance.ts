"use client";

import { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

export function useLogMaintenance(initialDays: number, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [logsRetentionDays, setLogsRetentionDays] = useState<number>(initialDays);
  const [isPurgingLogs, setIsPurgingLogs] = useState<boolean>(false);
  const handleSaveLogsRetention = async (days: number) => {
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ logs_retention_days: days }),
      });
      if (res.ok) {
        showToast(t("settingsPage.retentionSaved"), "success");
      } else {
        showToast(t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handlePurgeLogs = async () => {
    if (!window.confirm(t("settingsPage.purgeConfirm"))) return;
    setIsPurgingLogs(true);
    try {
      const res = await fetch(getApiUrl("/settings/logs/purge"), { method: "POST" });
      const body = await res.json();
      if (res.ok) {
        const details = body.details;
        const msg = details
          ? t("settingsPage.purgeDone", { logs: details.purged_logs, metrics: details.purged_metrics })
          : (body.message || t("settingsPage.logsPurgedSuccess"));
        showToast(msg, "success");
      } else {
        showToast(errorMessage(body, t("settingsPage.saveError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setIsPurgingLogs(false);
    }
  };

  return { logsRetentionDays, setLogsRetentionDays, isPurgingLogs, handleSaveLogsRetention, handlePurgeLogs };
}
