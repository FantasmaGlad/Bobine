"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";

export default function SimplifiedUiToggle() {
  const { simplifiedUi, setSimplifiedUi, t } = useAppSettings();
  return (
  <div className="form-group" style={{ maxWidth: "520px" }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }}>
      <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>{t("settingsPage.simplifiedUiLabel")}</span>
      <label className="ra-switch" title={t("settingsPage.simplifiedUiLabel")}>
        <input type="checkbox" checked={simplifiedUi} onChange={(e) => setSimplifiedUi(e.target.checked)} />
        <span className="ra-switch-track" />
      </label>
    </div>
    <p className="settings-hint">{t("settingsPage.simplifiedUiHint")}</p>
  </div>
  );
}
