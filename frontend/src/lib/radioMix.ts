/**
 * Table de mixage applicative d'une sortie radio (phase 3 des périphériques) — logique PURE, sans DOM ni Web Audio.
 *
 * Trois tranches : « Musique » (son = `RadioSoundSettings` de la sortie, déjà existant), « Rappels » (avec leur propre
 * égaliseur, neutre par défaut) et « Sortie » (gain et sourdine après les deux). Le serveur valide par bornage, stocke et
 * diffuse (`RadioState.mix`) ; le lecteur `/radio` traduit ces réglages en gains Web Audio (`radioMixGraph.ts`).
 * Les bornes DOIVENT rester alignées sur `backend/app/utils/radio_mix.py`.
 */
import { clampSound, defaultSound, LIMITER_OFF, LIMITER_ON, type LimiterParams, type RadioSoundSettings } from "./radioSound.ts";

export const GAIN_MIN_DB = -40;
export const GAIN_MAX_DB = 6;

export type StripId = "music" | "announcements";
export type MeterId = StripId | "master";

export interface MixStrip {
  /** Gain du fader en dB (−40…+6), pas de 1. */
  gain_db: number;
  muted: boolean;
  /** Solo : tant qu'une tranche est en solo, les autres tranches sont coupées. */
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

/**
 * Réglages valides à partir d'une entrée quelconque : bornés (jamais d'exception), les champs absents ou invalides
 * gardent la valeur de `base`. Même règle que le serveur (`sanitize_mix`), qui reste l'autorité.
 */
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

/** Gain linéaire d'un réglage en dB. */
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

/** Gains linéaires réellement appliqués : sourdine, fader et règle du solo (les tranches hors solo sont coupées). */
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
  /** Égaliseur des rappels. */
  announcementsSound: RadioSoundSettings;
  /** Limiteur de sortie : actif seulement si un fader relève le son (sinon la musique reste strictement inchangée). */
  limiter: LimiterParams;
}

export function toMixerParams(mix: RadioMix): MixerParams {
  const boost = mix.master.gain_db > 0 || mix.music.gain_db > 0 || mix.announcements.gain_db > 0;
  return { ...effectiveGains(mix), announcementsSound: mix.announcements.sound, limiter: boost ? LIMITER_ON : LIMITER_OFF };
}

/** Une tranche est-elle audible ? (pour l'affichage : sourdine, solo d'une autre tranche, fader au plancher). */
export function stripAudible(mix: RadioMix, id: StripId): boolean {
  return effectiveGains(mix)[id] > 0 && effectiveGains(mix).master > 0;
}

// ---------------------------------------------------------------------------
// Vumètre
// ---------------------------------------------------------------------------

/** Plancher du vumètre (dBFS) : en dessous, l'aiguille reste à 0. */
export const METER_FLOOR_DB = -60;

/** Amplitude crête (0…1) → niveau d'affichage 0…100 (échelle dBFS −60…0). */
export function meterLevel(peak: number): number {
  if (!Number.isFinite(peak) || peak <= 0) return 0;
  const db = 20 * Math.log10(Math.min(1, peak));
  return Math.max(0, Math.min(100, Math.round(((db - METER_FLOOR_DB) / -METER_FLOOR_DB) * 100)));
}

/** Retombée douce de l'aiguille : monte tout de suite, redescend d'au plus `fall` points par mesure. */
export function smoothLevel(previous: number, next: number, fall = 12): number {
  return next >= previous ? next : Math.max(next, previous - fall);
}

export function formatDb(db: number): string {
  return `${db > 0 ? "+" : ""}${db} dB`;
}
