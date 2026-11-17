"use client";

import React, { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

interface LidInfo {
  has_lid: boolean;
  prevent_sleep: boolean;
}

const BOX: React.CSSProperties = {
  marginTop: "16px",
  padding: "16px 20px",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-surface-elevated)",
  border: "1px solid var(--border-color)",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "16px",
  flexWrap: "wrap",
};
const TOGGLE: React.CSSProperties = { display: "inline-flex", borderRadius: "var(--radius-md)", overflow: "hidden", border: "1px solid var(--border-color)", background: "var(--bg-surface-elevated)" };
const CHOICE: React.CSSProperties = { borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 };

export default function LidSetting({ showToast }: { showToast: ShowToast }) {
  const { t } = useAppSettings();
  const [lidInfo, setLidInfo] = useState<LidInfo | null>(null);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    fetch(getApiUrl("/settings/laptop-lid"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((info) => {
        if (info) setLidInfo(info);
      })
      .catch(() => {});
  }, []);

  const toggle = async (preventSleep: boolean) => {
    setUpdating(true);
    try {
      const res = await fetch(getApiUrl("/settings/laptop-lid"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prevent_sleep: preventSleep }),
      });
      if (res.ok) {
        setLidInfo(await res.json());
        showToast(t("settingsPage.clamshellApplied"), "success");
      } else {
        showToast(t("settingsPage.clamshellError"), "error");
      }
    } catch {
      showToast(t("settingsPage.clamshellError"), "error");
    } finally {
      setUpdating(false);
    }
  };

  if (!lidInfo?.has_lid) return null;
  return (
    <div style={BOX}>
      <div style={{ flex: "1 1 280px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, fontSize: "0.95rem", color: "var(--text-main)" }}>
          <Icon name="laptop" size={20} />
          <span>{t("settingsPage.clamshellToggle")}</span>
        </div>
        <p className="settings-hint" style={{ margin: "4px 0 0 28px", fontSize: "0.85rem" }}>{t("settingsPage.clamshellDesc")}</p>
      </div>
      <div style={TOGGLE}>
        <button type="button" className={`btn btn-sm ${lidInfo.prevent_sleep ? "btn-primary" : "btn-secondary"}`} style={CHOICE} onClick={() => toggle(true)} disabled={updating}>
          {t("common.yes")}
        </button>
        <button type="button" className={`btn btn-sm ${!lidInfo.prevent_sleep ? "btn-primary" : "btn-secondary"}`} style={CHOICE} onClick={() => toggle(false)} disabled={updating}>
          {t("common.no")}
        </button>
      </div>
    </div>
  );
}
