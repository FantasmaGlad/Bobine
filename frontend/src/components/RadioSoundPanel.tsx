"use client";

import React, { useEffect, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import {
  BAND_FREQUENCIES,
  BAND_GAIN_MAX_DB,
  BAND_GAIN_MIN_DB,
  BASS_BOOST_MAX_DB,
  PRESETS,
  applyPreset,
  clampSound,
  defaultSound,
  knownPresetId,
  matchingPreset,
  type RadioSoundSettings,
} from "@/lib/radioSound";

// Gestion du son d'UNE sortie radio : égaliseur 5 bandes, basses, préréglages, loudness et
// protection anti-saturation. Le traitement est fait par le lecteur (graphe Web Audio) ; ce
// panneau n'envoie que les réglages (`radio_set_sound`), que le serveur borne, persiste et
// rediffuse à tous les lecteurs et télécommandes de la sortie.
//
// Sliders HORIZONTAUX (et non verticaux) : un range vertical (writing-mode) n'est pas rendu par
// Firefox ESR, cible de support officielle — une rangée par bande reste lisible partout, au
// toucher comme à la télécommande.

/** Délai avant d'envoyer le dernier réglage pendant un glissement (évite une écriture en base par pas). */
const SEND_DELAY_MS = 120;
/** Durée pendant laquelle le réglage local prime sur l'état serveur après un envoi. */
const DRAFT_HOLD_MS = 600;

function formatFrequency(hz: number): string {
  return hz >= 1000 ? `${hz / 1000} kHz` : `${hz} Hz`;
}

function formatGain(db: number): string {
  return `${db > 0 ? "+" : ""}${db} dB`;
}

interface RadioSoundPanelProps {
  /** Réglages courants de la sortie (champ `sound` de l'état diffusé). */
  sound: RadioSoundSettings;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  /** "compact" : sans bandes détaillées, pour les écrans étroits (préréglages, basses, interrupteurs). */
  variant?: "full" | "compact";
}

export default function RadioSoundPanel({ sound, sendCommand, variant = "full" }: RadioSoundPanelProps) {
  const { t } = useAppSettings();
  // Réglage local pendant un glissement : l'état serveur n'arrive qu'après l'aller-retour, le
  // curseur ne doit pas « sauter » entre-temps.
  const [draft, setDraft] = useState<RadioSoundSettings | null>(null);
  const sendTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const current = draft ?? sound;

  useEffect(
    () => () => {
      if (sendTimerRef.current) clearTimeout(sendTimerRef.current);
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    },
    [],
  );

  const commit = (next: RadioSoundSettings) => {
    const bounded = clampSound(next, current);
    setDraft(bounded);
    if (sendTimerRef.current) clearTimeout(sendTimerRef.current);
    sendTimerRef.current = setTimeout(() => {
      sendCommand("radio_set_sound", { sound: bounded });
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
      holdTimerRef.current = setTimeout(() => setDraft(null), DRAFT_HOLD_MS);
    }, SEND_DELAY_MS);
  };

  // Un réglage manuel quitte le préréglage appliqué, sauf s'il en recrée exactement un.
  const setManual = (patch: Partial<RadioSoundSettings>) => {
    const merged = clampSound(patch, current);
    commit({ ...merged, preset: matchingPreset(merged) });
  };

  // Un identifiant mémorisé qui n'existe plus (ancien préréglage) compte comme un réglage manuel.
  const activePreset = knownPresetId(current.preset) ?? matchingPreset(current);

  return (
    <div className={`radio-sound-panel radio-sound-panel--${variant}`}>
      <div className="radio-sound-head">
        <span className="radio-sound-title">{t("radioSound.title")}</span>
        <label className="radio-sound-switch" title={t("radioSound.enabledHint")}>
          <input
            type="checkbox"
            checked={current.enabled}
            onChange={(e) => commit({ ...current, enabled: e.target.checked })}
          />
          <span>{current.enabled ? t("radioSound.enabledOn") : t("radioSound.enabledOff")}</span>
        </label>
      </div>

      <div className="radio-sound-presets" role="group" aria-label={t("radioSound.presetsLabel")}>
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`radio-sound-chip olc-press ${activePreset === preset.id ? "active" : ""}`}
            aria-pressed={activePreset === preset.id}
            disabled={!current.enabled}
            onClick={() => commit(applyPreset(preset.id, current))}
          >
            {t(`radioSound.presets.${preset.id}`)}
          </button>
        ))}
      </div>

      {variant === "full" && (
        <div className="radio-sound-bands" aria-label={t("radioSound.bandsLabel")}>
          {BAND_FREQUENCIES.map((frequency, i) => (
            <label key={frequency} className="radio-sound-row">
              <span className="radio-sound-row-label">{formatFrequency(frequency)}</span>
              <input
                type="range"
                min={BAND_GAIN_MIN_DB}
                max={BAND_GAIN_MAX_DB}
                step={1}
                value={current.bands[i]}
                disabled={!current.enabled}
                onChange={(e) => {
                  const bands = [...current.bands];
                  bands[i] = Number(e.target.value);
                  setManual({ bands });
                }}
                className="volume-slider"
                aria-label={`${formatFrequency(frequency)}`}
              />
              <span className="radio-sound-row-value">{formatGain(current.bands[i])}</span>
            </label>
          ))}
        </div>
      )}

      <label className="radio-sound-row">
        <span className="radio-sound-row-label">{t("radioSound.bass")}</span>
        <input
          type="range"
          min={0}
          max={BASS_BOOST_MAX_DB}
          step={1}
          value={current.bass_boost}
          disabled={!current.enabled}
          onChange={(e) => setManual({ bass_boost: Number(e.target.value) })}
          className="volume-slider"
          aria-label={t("radioSound.bass")}
        />
        <span className="radio-sound-row-value">{formatGain(current.bass_boost)}</span>
      </label>

      <div className="radio-sound-toggles">
        <label className="radio-sound-switch" title={t("radioSound.loudnessHint")}>
          <input
            type="checkbox"
            checked={current.loudness}
            disabled={!current.enabled}
            onChange={(e) => setManual({ loudness: e.target.checked })}
          />
          <span>{t("radioSound.loudness")}</span>
        </label>
        <label className="radio-sound-switch" title={t("radioSound.limiterHint")}>
          <input
            type="checkbox"
            checked={current.limiter}
            disabled={!current.enabled}
            onChange={(e) => commit({ ...current, limiter: e.target.checked })}
          />
          <span>{t("radioSound.limiter")}</span>
        </label>
        <button
          type="button"
          className="btn btn-secondary radio-sound-reset"
          onClick={() => commit({ ...defaultSound(), limiter: current.limiter })}
        >
          {t("radioSound.reset")}
        </button>
      </div>
    </div>
  );
}
