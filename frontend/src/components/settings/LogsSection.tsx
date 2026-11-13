"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

export default function LogsSection({ hidden, initialDays, showToast }: { hidden: boolean; initialDays: number; showToast: ShowToast }) {
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

  return (
      <section className="live-block" id="section-logs" hidden={hidden}>
        <h3><Icon name="auto_delete" size={18} /> {t("settingsPage.logsMaintenanceSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.logsMaintenanceHint")}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <label style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-main)" }}>
              {t("settingsPage.logsRetentionDaysLabel")} :
            </label>
            <input
              type="number"
              min={1}
              max={365}
              value={logsRetentionDays}
              onChange={(e) => setLogsRetentionDays(Math.max(1, parseInt(e.target.value) || 1))}
              onBlur={() => handleSaveLogsRetention(logsRetentionDays)}
              style={{
                width: "80px",
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-color)",
                background: "var(--bg-surface-elevated)",
                color: "var(--text-main)",
                fontSize: "0.95rem",
                fontWeight: 700,
                textAlign: "center",
              }}
            />
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {t("settingsPage.logsRetentionDaysHint")}
            </span>
          </div>
          <div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ height: "42px", display: "inline-flex", alignItems: "center", gap: "8px" }}
              onClick={handlePurgeLogs}
              disabled={isPurgingLogs}
            >
              <Icon name="delete_sweep" size={18} />
              {isPurgingLogs ? t("settingsPage.logsPurging") : t("settingsPage.logsPurgeNow")}
            </button>
          </div>
        </div>
      </section>
  );
}
