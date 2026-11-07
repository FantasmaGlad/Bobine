"use client";

import { useCallback, useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { SETTING_BOUNDS, TIMING_SETTING_KEYS, parseBounded, type TimingSettingKey } from "@/lib/settingsBounds";

type Status = "idle" | "saved" | "error";

/**
 * Réglages → Lecture et médias : attente entre deux cours, volume de départ, minuterie des pistes audio et fondu des
 * rappels radio. Les bornes sont celles du serveur (`lib/settingsBounds.ts`) ; une valeur est enregistrée à la validation
 * du champ (sortie du champ ou Entrée) et seulement si elle est dans la plage.
 */
export default function PlaybackTimingSettings() {
  const { t } = useAppSettings();
  const [saved, setSaved] = useState<Partial<Record<TimingSettingKey, number>>>({});
  const [draft, setDraft] = useState<Partial<Record<TimingSettingKey, string>>>({});
  const [status, setStatus] = useState<Partial<Record<TimingSettingKey, Status>>>({});

  const load = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl("/settings"), { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const values: Partial<Record<TimingSettingKey, number>> = {};
      for (const key of TIMING_SETTING_KEYS) if (typeof data[key] === "number") values[key] = data[key];
      setSaved(values);
    } catch {
      /* hors ligne : les champs restent vides */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial des valeurs du serveur
    void load();
  }, [load]);

  const commit = async (key: TimingSettingKey) => {
    const text = draft[key];
    if (text === undefined) return;
    const value = parseBounded(key, text);
    if (value === null) {
      setStatus((s) => ({ ...s, [key]: "error" }));
      return;
    }
    if (value === saved[key]) {
      setDraft((d) => ({ ...d, [key]: undefined }));
      return;
    }
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: value }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setSaved((s) => ({ ...s, [key]: value }));
      setDraft((d) => ({ ...d, [key]: undefined }));
      setStatus((s) => ({ ...s, [key]: "saved" }));
    } catch {
      setStatus((s) => ({ ...s, [key]: "error" }));
    }
  };

  return (
    <section className="live-block" aria-labelledby="timing-title">
      <h3 id="timing-title">{t("settingsPage.timing.title")}</h3>
      <p className="settings-hint">{t("settingsPage.timing.intro")}</p>
      <div className="settings-timing-grid">
        {TIMING_SETTING_KEYS.map((key) => {
          const { min, max, unit } = SETTING_BOUNDS[key];
          const shown = draft[key] ?? (saved[key] === undefined ? "" : String(saved[key]));
          const state = status[key] ?? "idle";
          return (
            <div className="form-group" key={key}>
              <label className="form-label" htmlFor={`timing-${key}`}>{t(`settingsPage.timing.${key}.label`)}</label>
              <div className="settings-timing-field">
                <input
                  id={`timing-${key}`}
                  className="form-control"
                  type="number"
                  inputMode="numeric"
                  min={min}
                  max={max}
                  step={1}
                  value={shown}
                  aria-invalid={state === "error"}
                  aria-describedby={`timing-${key}-hint`}
                  onChange={(e) => {
                    setDraft((d) => ({ ...d, [key]: e.target.value }));
                    setStatus((s) => ({ ...s, [key]: "idle" }));
                  }}
                  onBlur={() => void commit(key)}
                  onKeyDown={(e) => { if (e.key === "Enter") void commit(key); }}
                />
                <span className="settings-timing-unit">{unit}</span>
              </div>
              <p id={`timing-${key}-hint`} className="settings-hint" role={state === "idle" ? undefined : "status"}>
                {state === "saved" ? t("settingsPage.timing.saved")
                  : state === "error" ? t("settingsPage.timing.invalid", { min, max, unit })
                  : t(`settingsPage.timing.${key}.hint`, { min, max, unit })}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
