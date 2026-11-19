"use client";

import SegmentedTabs from "@/components/SegmentedTabs";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { paletteOf, THEME_MODES, THEMES, type ThemeMode } from "@/lib/themePalettes";

export default function ThemePicker() {
  const { theme, themeMode, resolvedMode, setTheme, setThemeMode, t } = useAppSettings();
  return (
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
  );
}
