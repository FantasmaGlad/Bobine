import { clampSound, defaultSound, LIMITER_OFF, LIMITER_ON, type LimiterParams, type RadioSoundSettings } from "./radioSound.ts";

export const GAIN_MIN_DB = -40;
export const GAIN_MAX_DB = 6;

export type StripId = "music" | "announcements";
export type MeterId = StripId | "master";

export interface MixStrip {
  gain_db: number;
  muted: boolean;
  solo: boolean;
}

export interface MixMaster {
  gain_db: number;
  muted: boolean;
}

export interface RadioMix {
  master: MixMaster;
  music: MixStrip;
  announcements: MixStrip & { sound: RadioSoundSettings };
}

export function defaultMix(): RadioMix {
  return {
    master: { gain_db: 0, muted: false },
    music: { gain_db: 0, muted: false, solo: false },
    announcements: { gain_db: 0, muted: false, solo: false, sound: defaultSound() },
  };
}

function clampGain(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.max(GAIN_MIN_DB, Math.min(GAIN_MAX_DB, Math.round(value)));
}

const flag = (value: unknown, fallback: boolean): boolean => (typeof value === "boolean" ? value : fallback);

type Loose<T> = { [K in keyof T]?: T[K] extends object ? Loose<T[K]> : T[K] };

export function clampMix(raw: Loose<RadioMix> | null | undefined, base: RadioMix = defaultMix()): RadioMix {
  const input = (raw ?? {}) as Loose<RadioMix>;
  const section = <K extends "music" | "announcements">(name: K) => {
    const incoming = (input[name] ?? {}) as Partial<MixStrip>;
    const previous = base[name];
    return {
      gain_db: clampGain(incoming.gain_db, clampGain(previous.gain_db, 0)),
      muted: flag(incoming.muted, flag(previous.muted, false)),
      solo: flag(incoming.solo, flag(previous.solo, false)),
    };
  };
  const master = (input.master ?? {}) as Partial<MixMaster>;
  return {
    master: {
      gain_db: clampGain(master.gain_db, clampGain(base.master.gain_db, 0)),
      muted: flag(master.muted, flag(base.master.muted, false)),
    },
    music: section("music"),
    announcements: {
      ...section("announcements"),
      sound: clampSound((input.announcements?.sound ?? null) as Partial<RadioSoundSettings> | null, base.announcements.sound),
    },
  };
}

export function dbToGain(db: number): number {
  return Math.pow(10, db / 20);
}

export function hasSolo(mix: RadioMix): boolean {
  return mix.music.solo || mix.announcements.solo;
}

export interface EffectiveGains {
  music: number;
  announcements: number;
  master: number;
}

export function effectiveGains(mix: RadioMix): EffectiveGains {
  const solo = hasSolo(mix);
  const strip = (s: MixStrip) => (s.muted || (solo && !s.solo) ? 0 : dbToGain(s.gain_db));
  return {
    music: strip(mix.music),
    announcements: strip(mix.announcements),
    master: mix.master.muted ? 0 : dbToGain(mix.master.gain_db),
  };
}

export interface MixerParams extends EffectiveGains {
  announcementsSound: RadioSoundSettings;
  limiter: LimiterParams;
}

export function toMixerParams(mix: RadioMix): MixerParams {
  const boost = mix.master.gain_db > 0 || mix.music.gain_db > 0 || mix.announcements.gain_db > 0;
  return { ...effectiveGains(mix), announcementsSound: mix.announcements.sound, limiter: boost ? LIMITER_ON : LIMITER_OFF };
}

export function stripAudible(mix: RadioMix, id: StripId): boolean {
  return effectiveGains(mix)[id] > 0 && effectiveGains(mix).master > 0;
}

export const METER_FLOOR_DB = -60;

export function meterLevel(peak: number): number {
  if (!Number.isFinite(peak) || peak <= 0) return 0;
  const db = 20 * Math.log10(Math.min(1, peak));
  return Math.max(0, Math.min(100, Math.round(((db - METER_FLOOR_DB) / -METER_FLOOR_DB) * 100)));
}

export function smoothLevel(previous: number, next: number, fall = 12): number {
  return next >= previous ? next : Math.max(next, previous - fall);
}

export function formatDb(db: number): string {
  return `${db > 0 ? "+" : ""}${db} dB`;
}
