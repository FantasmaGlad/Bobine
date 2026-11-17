"use client";

import React from "react";
import type { SettingsData } from "../types";

interface AutoUpdateSettingsProps {
  t: (key: string) => string;
  data: SettingsData;
  setData: React.Dispatch<React.SetStateAction<SettingsData | null>>;
  onChange: (patch: { auto_update_enabled?: "true" | "false"; auto_update_time?: string }) => void;
}

export default function AutoUpdateSettings({ t, data, setData, onChange }: AutoUpdateSettingsProps) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
        <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
          {t("settingsPage.autoUpdateSection")}
        </span>
        <label className="ra-switch" title={t("settingsPage.autoUpdateToggleLabel")}>
          <input
            type="checkbox"
            checked={data.auto_update_enabled === "true"}
            onChange={(e) => onChange({ auto_update_enabled: e.target.checked ? "true" : "false" })}
          />
          <span className="ra-switch-track" />
        </label>
      </div>
      {data.auto_update_enabled === "true" && (
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <label htmlFor="auto-update-time" className="form-label" style={{ margin: 0 }}>
            {t("settingsPage.autoUpdateTimeLabel")}
          </label>
          <input
            id="auto-update-time"
            type="time"
            className="form-control"
            style={{ maxWidth: "140px" }}
            value={data.auto_update_time}
            onChange={(e) => setData({ ...data, auto_update_time: e.target.value })}
            onBlur={(e) => onChange({ auto_update_time: e.target.value })}
          />
        </div>
      )}
      <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.autoUpdateToggleHint")}</p>
    </>
  );
}
