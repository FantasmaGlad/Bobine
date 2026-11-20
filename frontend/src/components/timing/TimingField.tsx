"use client";

import { SETTING_BOUNDS, type TimingSettingKey } from "@/lib/settingsBounds";
import { type TimingStatus } from "./useTimingSettings";

type T = (key: string, params?: Record<string, string | number>) => string;

interface FieldProps {
  settingKey: TimingSettingKey;
  shown: string;
  state: TimingStatus;
  onEdit: (text: string) => void;
  onCommit: () => void;
  t: T;
}

function hintText(settingKey: TimingSettingKey, state: TimingStatus, t: T): string {
  const { min, max, unit } = SETTING_BOUNDS[settingKey];
  if (state === "saved") return t("settingsPage.timing.saved");
  if (state === "error") return t("settingsPage.timing.invalid", { min, max, unit });
  return t(`settingsPage.timing.${settingKey}.hint`, { min, max, unit });
}

export default function TimingField({ settingKey: key, shown, state, onEdit, onCommit, t }: FieldProps) {
  const { min, max, unit } = SETTING_BOUNDS[key];
  return (
    <div className="form-group">
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
          onChange={(e) => onEdit(e.target.value)}
          onBlur={onCommit}
          onKeyDown={(e) => { if (e.key === "Enter") onCommit(); }}
        />
        <span className="settings-timing-unit">{unit}</span>
      </div>
      <p id={`timing-${key}-hint`} className="settings-hint" role={state === "idle" ? undefined : "status"}>
        {hintText(key, state, t)}
      </p>
    </div>
  );
}
