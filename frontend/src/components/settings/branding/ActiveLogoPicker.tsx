"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";

export default function ActiveLogoPicker() {
  const { t, activeLogo, setActiveLogo } = useAppSettings();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
      <span className="form-label" style={{ margin: 0, fontSize: "0.85rem" }}>
        {t("settingsPage.activeLogoLabel")}
      </span>
      <div
        style={{
          display: "inline-flex",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
          border: "1px solid var(--border-color)",
          background: "var(--bg-surface-elevated)",
        }}
      >
        <button
          type="button"
          className={`btn btn-sm ${activeLogo === "default" ? "btn-primary" : "btn-secondary"}`}
          style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
          onClick={() => setActiveLogo("default")}
        >
          {t("settingsPage.logoBobine")}
        </button>
        <button
          type="button"
          className={`btn btn-sm ${activeLogo === "custom" ? "btn-primary" : "btn-secondary"}`}
          style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
          onClick={() => setActiveLogo("custom")}
        >
          {t("settingsPage.logoCustom")}
        </button>
      </div>
    </div>
  );
}
