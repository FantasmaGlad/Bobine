"use client";

import { useState, type ReactNode } from "react";
import Icon from "@/components/Icon";
import RadioSoundPanel from "@/components/RadioSoundPanel";
import { formatDb, GAIN_MAX_DB, GAIN_MIN_DB } from "@/lib/radioMix";
import { clampSound, type RadioSoundSettings } from "@/lib/radioSound";
import { type SectionProps } from "../shared/section";

export interface Fader {
  gain: number;
  muted: boolean;
  level: number | undefined;
  onGain: (db: number) => void;
  onMute: () => void;
}

interface Props {
  icon: string;
  title: string;
  sub?: string;
  nested?: boolean;
  output?: ReactNode;
  fader?: Fader;
  sound: RadioSoundSettings;
  onSound: (sound: RadioSoundSettings) => void;
  t: SectionProps["t"];
}

function Meter({ level, label }: { level: number | undefined; label: string }) {
  const value = level ?? 0;
  return (
    <div className="sd-meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
      <div className={`sd-meter-fill${value >= 92 ? " is-hot" : ""}`} style={{ transform: `scaleX(${value / 100})` }} />
    </div>
  );
}

function FaderCell({ fader, title, t }: { fader: Fader; title: string; t: SectionProps["t"] }) {
  return (
    <div className="sd-fader">
      <Meter level={fader.muted ? 0 : fader.level} label={t("devices.mixer.meter", { name: title })} />
      <input type="range" min={GAIN_MIN_DB} max={GAIN_MAX_DB} step={1} value={fader.gain}
        aria-label={`${title} — ${t("devices.mixer.level")}`} onChange={(e) => fader.onGain(Number(e.target.value))} />
      <span className="dv-value">{formatDb(fader.gain)}</span>
      <button type="button" className={`btn btn-icon sd-mute${fader.muted ? " is-on" : ""}`} aria-pressed={fader.muted}
        title={fader.muted ? t("devices.audio.unmute") : t("devices.audio.mute")} onClick={fader.onMute}>
        <Icon name={fader.muted ? "volume_off" : "volume_up"} size={18} />
      </button>
    </div>
  );
}

export default function SoundRow({ icon, title, sub, nested = false, output, fader, sound, onSound, t }: Props) {
  const [eqOpen, setEqOpen] = useState(false);
  return (
    <div className={`sd-row${nested ? " sd-row--nested" : ""}${fader?.muted ? " is-silent" : ""}`}>
      <div className="sd-name">
        <span className="dv-icon"><Icon name={icon} size={20} /></span>
        <span className="dv-text">
          <span className="dv-title">{title}</span>
          {sub && <span className="dv-sub">{sub}</span>}
        </span>
      </div>
      <div className="sd-output">{output}</div>
      {fader ? <FaderCell fader={fader} title={title} t={t} /> : <div className="sd-fader" />}
      <button type="button" className={`btn btn-secondary sd-eq-btn${eqOpen ? " is-on" : ""}`} aria-expanded={eqOpen} onClick={() => setEqOpen((v) => !v)}>
        <Icon name="tune" size={16} /> {t("devices.mixer.equalizer")}
      </button>
      {eqOpen && (
        <div className="sd-eq">
          <RadioSoundPanel sound={sound}
            sendCommand={(command, params) => { if (command === "radio_set_sound") onSound(clampSound(params?.sound as RadioSoundSettings, sound)); }} />
        </div>
      )}
    </div>
  );
}
