"use client";
import React, { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SegmentedTabs from "@/components/SegmentedTabs";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { loadMode, saveMode, type GlassMode } from "@/lib/glassQuality";
import type { Language } from "@/lib/i18n";
import { paletteOf, THEME_MODES, THEMES, type ThemeMode } from "@/lib/themePalettes";
import type { SettingsData } from "./types";

export default function AppearanceSection({ hidden, data }: { hidden: boolean; data: SettingsData }) {
  const { theme, themeMode, resolvedMode, storedLanguage, languagePending, simplifiedUi, setSimplifiedUi, setTheme, setThemeMode, setLanguage, t } = useAppSettings();
  const [glassMode, setGlassMode] = useState<GlassMode>("auto");
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- relit le réglage mémorisé dans le navigateur au montage
    setGlassMode(loadMode());
  }, []);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);
  const restartNow = async () => {
    setRestarting(true);
    setRestartMessage(null);
    try {
      const res = await fetch(getApiUrl("/settings/system/restart"), { method: "POST" });
      setRestartMessage(t(res.ok ? "settingsPage.languageRestarting" : "settingsPage.languageRestartFailed"));
      if (!res.ok) setRestarting(false);
      else {
        window.setTimeout(() => {
          setRestarting(false);
          setRestartMessage(t("settingsPage.languageRestartFailed"));
        }, 30000);
      }
    } catch {
      setRestartMessage(t("settingsPage.languageRestartFailed"));
      setRestarting(false);
    }
  };

  return (
      <section className="live-block" id="section-appearance" hidden={hidden}>
        <h3><Icon name="palette" size={18} /> {t("settingsPage.appearanceSection")}</h3>
        <div className="form-group">
          <label className="form-label">{t("settingsPage.themeLabel")}</label>

          <SegmentedTabs
            ariaLabel={t("settingsPage.themeModeLabel")}
            value={themeMode}
            onChange={(id) => setThemeMode(id as ThemeMode)}
            tabs={THEME_MODES.map((mode) => ({
              id: mode,
              icon: mode === "auto" ? "brightness_auto" : mode === "light" ? "light_mode" : "dark_mode",
              label: t(`settingsPage.themeMode${mode === "auto" ? "Auto" : mode === "light" ? "Light" : "Dark"}`),
            }))}
          />
          <p className="settings-hint">{t("settingsPage.themeModeHint")}</p>

          <div className="theme-picker-grid">
            {THEMES.map((option) => {
              const palette = paletteOf(option.id, resolvedMode);
              return (
                <button
                  key={option.id}
                  type="button"
                  className={`theme-picker-card ${theme === option.id ? "active" : ""}`}
                  aria-pressed={theme === option.id}
                  onClick={() => setTheme(option.id)}
                >
                  <div className="theme-picker-swatch">
                    {[palette.bg, palette.surface, palette.accent, palette.text].map((color, i) => (
                      <span key={i} style={{ background: color }} />
                    ))}
                  </div>
                  <span className="theme-picker-name">{t(option.labelKey)}</span>
                </button>
              );
            })}
          </div>

          <p className="settings-hint">{t("settingsPage.themeHint")}</p>
        </div>

        <div className="form-group" style={{ maxWidth: "320px" }}>
          <label className="form-label">{t("settingsPage.glassLabel")}</label>
          <ResponsiveSelect
            className="form-control"
            value={glassMode}
            onChange={(value) => { setGlassMode(value as GlassMode); saveMode(value as GlassMode); }}
            title={t("settingsPage.glassLabel")}
            options={[
              { value: "auto", label: t("settingsPage.glassAuto") },
              { value: "full", label: t("settingsPage.glassFull") },
              { value: "reduced", label: t("settingsPage.glassReduced") },
              { value: "off", label: t("settingsPage.glassOff") },
            ]}
          />
          <p className="settings-hint">{t("settingsPage.glassHint")}</p>
        </div>

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
      </section>
  );
}
