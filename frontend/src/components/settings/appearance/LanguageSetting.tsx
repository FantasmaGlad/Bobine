"use client";

import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Language } from "@/lib/i18n";
import type { SettingsData } from "../types";
import { useRestart } from "./useRestart";

export default function LanguageSetting({ data }: { data: SettingsData }) {
  const { storedLanguage, languagePending, setLanguage, t } = useAppSettings();
  const { restarting, restartMessage, restartNow } = useRestart();
  return (
  <div className="form-group" style={{ maxWidth: "320px" }}>
    <label className="form-label">{t("settingsPage.languageLabel")}</label>
    <ResponsiveSelect
      className="form-control"
      value={storedLanguage}
      onChange={(value) => setLanguage(value as Language)}
      title={t("settingsPage.languageLabel")}
      options={[
        { value: "fr", label: t("settingsPage.languageFr") },
        { value: "en", label: t("settingsPage.languageEn") },
      ]}
    />
    <p className="settings-hint">{t("settingsPage.languageHint")}</p>
    {languagePending && (
      <div className="settings-hint" role="status" style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
        <span>{t("settingsPage.languagePending", { language: storedLanguage === "fr" ? t("settingsPage.languageFr") : t("settingsPage.languageEn") })}</span>
        <button type="button" className="btn btn-secondary" onClick={() => void restartNow()} disabled={restarting}>
          {t("settingsPage.languageRestartNow")}
        </button>
        {data && data.restart_guaranteed === false && <span>{t("settingsPage.restartNotGuaranteed")}</span>}
        {restartMessage && <span>{restartMessage}</span>}
      </div>
    )}
  </div>
  );
}
