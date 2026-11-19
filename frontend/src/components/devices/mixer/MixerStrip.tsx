"use client";

import Icon from "@/components/Icon";
import { formatDb, GAIN_MAX_DB, GAIN_MIN_DB, type StripId } from "@/lib/radioMix";
import { type SectionProps } from "../common";

function MeterBar({ level, label }: { level: number | undefined; label: string }) {
  const value = level ?? 0;
  return (
    <div className="mx-meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
      <div className={`mx-meter-fill${value >= 92 ? " is-hot" : ""}`} style={{ transform: `scaleX(${value / 100})` }} />
    </div>
  );
}

export interface StripProps {
  id: StripId | "master";
  t: SectionProps["t"];
  gain: number;
  muted: boolean;
  solo?: boolean;
  silencedBySolo: boolean;
  level: number | undefined;
  onGain: (db: number) => void;
  onMute: () => void;
  onSolo?: () => void;
  children?: React.ReactNode;
}

function StripToggles({ t, muted, solo, onMute, onSolo }: StripProps) {
  return (
    <div className="mx-toggles">
      <button type="button" className={`mx-toggle mx-toggle--mute${muted ? " is-on" : ""}`} aria-pressed={muted} onClick={onMute}>
        <Icon name={muted ? "volume_off" : "volume_up"} size={16} /> {muted ? t("devices.audio.unmute") : t("devices.audio.mute")}
      </button>
      {onSolo && (
        <button type="button" className={`mx-toggle mx-toggle--solo${solo ? " is-on" : ""}`} aria-pressed={!!solo} onClick={onSolo}>
          <Icon name="headphones" size={16} /> {t("devices.mixer.solo")}
        </button>
      )}
    </div>
  );
}

export default function Strip(props: StripProps) {
  const { id, t, gain, muted, silencedBySolo, level, onGain, children } = props;
  const name = t(`devices.mixer.strips.${id}`);
  return (
    <div className={`mx-strip glass-interactive${muted || silencedBySolo ? " is-silent" : ""}`} data-strip={id}>
      <div className="mx-strip-head">
        <span className="dv-title">{name}</span>
        {silencedBySolo && <span className="dv-badge dv-badge--muted">{t("devices.mixer.silencedBySolo")}</span>}
      </div>
      <MeterBar level={level} label={t("devices.mixer.meter", { name })} />
      <label className="mx-fader">
        <span className="mx-fader-label">{t("devices.mixer.level")}</span>
        <input
          type="range"
          min={GAIN_MIN_DB}
          max={GAIN_MAX_DB}
          step={1}
          value={gain}
          aria-label={`${name} — ${t("devices.mixer.level")}`}
          onChange={(e) => onGain(Number(e.target.value))}
        />
        <span className="dv-value">{formatDb(gain)}</span>
      </label>
      <StripToggles {...props} />
      {children}
    </div>
  );
}
