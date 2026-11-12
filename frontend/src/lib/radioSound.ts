export const BAND_COUNT = 5;
export const BAND_GAIN_MIN_DB = -12;
export const BAND_GAIN_MAX_DB = 12;
export const BASS_BOOST_MAX_DB = 12;

export interface RadioSoundSettings {
  enabled: boolean;
  bands: number[];
  bass_boost: number;
  loudness: boolean;
  limiter: boolean;
  preset: string | null;
}

export const DEFAULT_SOUND: RadioSoundSettings = {
  enabled: true,
  bands: [0, 0, 0, 0, 0],
  bass_boost: 0,
  loudness: false,
  limiter: true,
  preset: null,
};

export function defaultSound(): RadioSoundSettings {
  return { ...DEFAULT_SOUND, bands: [...DEFAULT_SOUND.bands] };
}

export const BAND_FREQUENCIES = [60, 230, 910, 3600, 14000] as const;
export const BAND_TYPES: BiquadFilterType[] = ["lowshelf", "peaking", "peaking", "peaking", "highshelf"];
const BAND_Q = [0.7, 1, 1, 1, 0.7];

export const BASS_FREQUENCY = 80;
export const LOUDNESS_LOW = { frequency: 100, gain: 4 };
export const LOUDNESS_HIGH = { frequency: 10000, gain: 3 };

export function isNeutralSound(sound: RadioSoundSettings): boolean {
  return !sound.enabled || (sound.bands.every((gain) => gain === 0) && sound.bass_boost === 0 && !sound.loudness);
}

const PREAMP_MAX_CUT_DB = 18;

export interface SoundPreset {
  id: string;
  bands: number[];
  bass_boost: number;
  loudness: boolean;
}

export const PRESETS: SoundPreset[] = [
  { id: "bass", bands: [5, 3, 0, -1, 0], bass_boost: 4, loudness: false },
  { id: "voice", bands: [-4, -2, 2, 4, 1], bass_boost: 0, loudness: false },
  { id: "soft", bands: [2, 1, 0, -2, -4], bass_boost: 0, loudness: false },
];

export function knownPresetId(id: string | null | undefined): string | null {
  return PRESETS.some((p) => p.id === id) ? (id as string) : null;
}

function clampInt(value: unknown, low: number, high: number, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.max(low, Math.min(high, Math.round(value)));
}

export function clampSound(raw: Partial<RadioSoundSettings> | null | undefined, base: RadioSoundSettings = DEFAULT_SOUND): RadioSoundSettings {
  const input = raw ?? {};
  const bands: number[] = [];
  for (let i = 0; i < BAND_COUNT; i++) {
    const previous = clampInt(base.bands?.[i], BAND_GAIN_MIN_DB, BAND_GAIN_MAX_DB, 0);
    const candidate = Array.isArray(input.bands) ? input.bands[i] : undefined;
    bands.push(clampInt(candidate, BAND_GAIN_MIN_DB, BAND_GAIN_MAX_DB, previous));
  }
  return {
    enabled: typeof input.enabled === "boolean" ? input.enabled : base.enabled,
    bands,
    bass_boost: clampInt(input.bass_boost, 0, BASS_BOOST_MAX_DB, clampInt(base.bass_boost, 0, BASS_BOOST_MAX_DB, 0)),
    loudness: typeof input.loudness === "boolean" ? input.loudness : base.loudness,
    limiter: typeof input.limiter === "boolean" ? input.limiter : base.limiter,
    preset: "preset" in input ? (typeof input.preset === "string" && input.preset ? input.preset : null) : base.preset,
  };
}

export function applyPreset(presetId: string, current: RadioSoundSettings): RadioSoundSettings {
  const preset = PRESETS.find((p) => p.id === presetId);
  if (!preset) return current;
  return clampSound(
    { bands: preset.bands, bass_boost: preset.bass_boost, loudness: preset.loudness, preset: preset.id },
    current,
  );
}

export function matchingPreset(sound: RadioSoundSettings): string | null {
  const found = PRESETS.find(
    (p) =>
      p.bass_boost === sound.bass_boost &&
      p.loudness === sound.loudness &&
      p.bands.every((gain, i) => gain === sound.bands[i]),
  );
  return found ? found.id : null;
}

export interface FilterParams {
  type: BiquadFilterType;
  frequency: number;
  gain: number;
  q: number;
}

export interface LimiterParams {
  threshold: number;
  knee: number;
  ratio: number;
  attack: number;
  release: number;
}

export interface SoundGraphParams {
  preampGain: number;
  bands: FilterParams[];
  bass: FilterParams;
  loudnessLow: FilterParams;
  loudnessHigh: FilterParams;
  limiter: LimiterParams;
}

export function peakBoostDb(sound: RadioSoundSettings): number {
  if (!sound.enabled) return 0;
  const lowEnd = sound.bands[0] + sound.bass_boost + (sound.loudness ? LOUDNESS_LOW.gain : 0);
  const highEnd = sound.bands[4] + (sound.loudness ? LOUDNESS_HIGH.gain : 0);
  return Math.max(0, lowEnd, sound.bands[1], sound.bands[2], sound.bands[3], highEnd);
}

export function computePreamp(sound: RadioSoundSettings): number {
  const cut = Math.min(PREAMP_MAX_CUT_DB, peakBoostDb(sound));
  return Math.pow(10, -cut / 20);
}

export const LIMITER_ON: LimiterParams = { threshold: -3, knee: 2, ratio: 20, attack: 0.003, release: 0.15 };
export const LIMITER_OFF: LimiterParams = { threshold: 0, knee: 0, ratio: 1, attack: 0.003, release: 0.25 };

export function toGraphParams(sound: RadioSoundSettings): SoundGraphParams {
  const active = sound.enabled;
  const bands = BAND_FREQUENCIES.map((frequency, i) => ({
    type: BAND_TYPES[i],
    frequency,
    gain: active ? sound.bands[i] : 0,
    q: BAND_Q[i],
  }));
  return {
    preampGain: computePreamp(sound),
    bands,
    bass: { type: "lowshelf", frequency: BASS_FREQUENCY, gain: active ? sound.bass_boost : 0, q: 0.7 },
    loudnessLow: { type: "lowshelf", frequency: LOUDNESS_LOW.frequency, gain: active && sound.loudness ? LOUDNESS_LOW.gain : 0, q: 0.7 },
    loudnessHigh: { type: "highshelf", frequency: LOUDNESS_HIGH.frequency, gain: active && sound.loudness ? LOUDNESS_HIGH.gain : 0, q: 0.7 },
    limiter: active && sound.limiter && peakBoostDb(sound) > 0 ? LIMITER_ON : LIMITER_OFF,
  };
}
