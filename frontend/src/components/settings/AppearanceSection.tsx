"use client";
import { useClientChoice } from "@/lib/useClientSnapshot";
import React from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { loadMode, saveMode, type GlassMode } from "@/lib/glassQuality";
import type { SettingsData } from "./types";
import LanguageSetting from "./appearance/LanguageSetting";
import SimplifiedUiToggle from "./appearance/SimplifiedUiToggle";
import ThemePicker from "./appearance/ThemePicker";

export default function AppearanceSection({ hidden, data }: { hidden: boolean; data: SettingsData }) {
  const { t } = useAppSettings();
  const [glassMode, setGlassMode] = useClientChoice<GlassMode>(loadMode, "auto");

  return (
      <section className="live-block" id="section-appearance" hidden={hidden}>
        <h3><Icon name="palette" size={18} /> {t("settingsPage.appearanceSection")}</h3>
        <ThemePicker />
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
        <LanguageSetting data={data} />
        <SimplifiedUiToggle />
      </section>
  );
}
