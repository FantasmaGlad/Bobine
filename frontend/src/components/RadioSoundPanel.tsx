"use client";

import React from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { knownPresetId, matchingPreset, type RadioSoundSettings } from "@/lib/radioSound";
import { BandSliders, BassSlider, PresetChips, SoundToggles } from "./radio-sound/SoundControls";
import { useSoundDraft } from "./radio-sound/useSoundDraft";

interface RadioSoundPanelProps {
  sound: RadioSoundSettings;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  variant?: "full" | "compact";
}

export default function RadioSoundPanel({ sound, sendCommand, variant = "full" }: RadioSoundPanelProps) {
  const { t } = useAppSettings();
  const { current, commit, setManual } = useSoundDraft(sound, sendCommand);
  const activePreset = knownPresetId(current.preset) ?? matchingPreset(current);
  const controls = { current, commit, setManual, t };

  return (
    <div className={`radio-sound-panel radio-sound-panel--${variant}`}>
      <div className="radio-sound-head">
        <span className="radio-sound-title">{t("radioSound.title")}</span>
        <label className="radio-sound-switch" title={t("radioSound.enabledHint")}>
          <input type="checkbox" checked={current.enabled} onChange={(e) => commit({ ...current, enabled: e.target.checked })} />
          <span>{current.enabled ? t("radioSound.enabledOn") : t("radioSound.enabledOff")}</span>
        </label>
      </div>
      <PresetChips {...controls} activePreset={activePreset} />
      {variant === "full" && <BandSliders {...controls} />}
      <BassSlider {...controls} />
      <SoundToggles {...controls} />
    </div>
  );
}
