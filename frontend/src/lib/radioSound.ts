/**
 * Réglages de son d'une sortie radio (égaliseur 5 bandes, basses, loudness, limiteur) —
 * logique PURE, sans accès au DOM ni à Web Audio, pour rester testable (`frontend/tests/`).
 *
 * Le serveur valide par bornage, stocke et diffuse ces réglages avec l'état de la sortie
 * (`RadioState.sound`) ; le lecteur `/radio` les traduit en paramètres de filtres Web
 * Audio. Les bornes ci-dessous DOIVENT rester alignées sur `backend/app/utils/radio_sound.py`.
 */

export const BAND_COUNT = 5;
export const BAND_GAIN_MIN_DB = -12;
export const BAND_GAIN_MAX_DB = 12;
export const BASS_BOOST_MAX_DB = 12;

export interface RadioSoundSettings {
  /** Contournement global : faux = son neutre, aucun filtre appliqué. */
  enabled: boolean;
  /** Gain (dB) des 5 bandes, du grave à l'aigu. */
  bands: number[];
  /** Renfort des basses (dB), indépendant des bandes. */
  bass_boost: number;
  /** Compensation « faible volume » (graves et aigus relevés). */
  loudness: boolean;
  /** Protection anti-saturation (compresseur de sécurité). */
  limiter: boolean;
  /** Identifiant du préréglage appliqué, null = réglage manuel. */
  preset: string | null;
}

export const DEFAULT_SOUND: RadioSoundSettings = {
  enabled: true,
  bands: [0, 0, 0, 0, 0],
  bass_boost: 0,
  loudness: false,
  limiter: true,
  preset: "flat",
};

export function defaultSound(): RadioSoundSettings {
  return { ...DEFAULT_SOUND, bands: [...DEFAULT_SOUND.bands] };
}

// ---------------------------------------------------------------------------
// Fréquences et préréglages
// ---------------------------------------------------------------------------

/** Fréquence centrale (Hz) de chaque bande : grave, bas-médium, médium, haut-médium, aigu. */
export const BAND_FREQUENCIES = [60, 230, 910, 3600, 14000] as const;
/** Forme du filtre de chaque bande : plateau aux extrémités, cloche au centre. */
export const BAND_TYPES: BiquadFilterType[] = ["lowshelf", "peaking", "peaking", "peaking", "highshelf"];
const BAND_Q = [0.7, 1, 1, 1, 0.7];

/** Renfort des basses : plateau bas indépendant des bandes. */
export const BASS_FREQUENCY = 80;
/** Compensation « faible volume » : graves et aigus relevés (courbes d'égale sonie, simplifiées). */
export const LOUDNESS_LOW = { frequency: 100, gain: 4 };
export const LOUDNESS_HIGH = { frequency: 10000, gain: 3 };

/** Plafond d'atténuation du préampli (dB) : évite un son anormalement faible. */
const PREAMP_MAX_CUT_DB = 18;

export interface SoundPreset {
  id: string;
  bands: number[];
  bass_boost: number;
  loudness: boolean;
}

export const PRESETS: SoundPreset[] = [
  { id: "flat", bands: [0, 0, 0, 0, 0], bass_boost: 0, loudness: false },
  { id: "voice", bands: [-4, -2, 2, 4, 1], bass_boost: 0, loudness: false },
  { id: "bass", bands: [5, 3, 0, -1, 0], bass_boost: 4, loudness: false },
  { id: "bright", bands: [-1, 0, 0, 3, 5], bass_boost: 0, loudness: false },
  { id: "cardio", bands: [4, 2, 0, 2, 3], bass_boost: 3, loudness: true },
  { id: "soft", bands: [2, 1, 0, -2, -4], bass_boost: 0, loudness: false },
];

// ---------------------------------------------------------------------------
// Bornage et préréglages
// ---------------------------------------------------------------------------

function clampInt(value: unknown, low: number, high: number, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.max(low, Math.min(high, Math.round(value)));
}

/**
 * Réglages valides à partir d'une entrée quelconque : bornés (jamais d'exception), les champs
 * absents ou invalides gardent la valeur de `base`. Même règle que le serveur
 * (`sanitize_sound`) — le serveur reste l'autorité, ceci évite l'aller-retour pour l'affichage.
 */
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

/** Applique un préréglage (les interrupteurs limiteur et activation sont conservés). */
export function applyPreset(presetId: string, current: RadioSoundSettings): RadioSoundSettings {
  const preset = PRESETS.find((p) => p.id === presetId);
  if (!preset) return current;
  return clampSound(
    { bands: preset.bands, bass_boost: preset.bass_boost, loudness: preset.loudness, preset: preset.id },
    current,
  );
}

/** Identifiant du préréglage correspondant exactement aux réglages, ou null (réglage manuel). */
export function matchingPreset(sound: RadioSoundSettings): string | null {
  const found = PRESETS.find(
    (p) =>
      p.bass_boost === sound.bass_boost &&
      p.loudness === sound.loudness &&
      p.bands.every((gain, i) => gain === sound.bands[i]),
  );
  return found ? found.id : null;
}

// ---------------------------------------------------------------------------
// Paramètres du graphe Web Audio
// ---------------------------------------------------------------------------

export interface FilterParams {
  type: BiquadFilterType;
  frequency: number;
  /** Gain en dB (0 = transparent). */
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
  /** Gain linéaire du préampli (≤ 1) compensant les relèvements pour éviter l'écrêtage. */
  preampGain: number;
  bands: FilterParams[];
  bass: FilterParams;
  loudnessLow: FilterParams;
  loudnessHigh: FilterParams;
  limiter: LimiterParams;
}

/** Pire relèvement (dB) cumulé sur la plage de fréquences, pour dimensionner le préampli. */
export function peakBoostDb(sound: RadioSoundSettings): number {
  if (!sound.enabled) return 0;
  const lowEnd = sound.bands[0] + sound.bass_boost + (sound.loudness ? LOUDNESS_LOW.gain : 0);
  const highEnd = sound.bands[4] + (sound.loudness ? LOUDNESS_HIGH.gain : 0);
  return Math.max(0, lowEnd, sound.bands[1], sound.bands[2], sound.bands[3], highEnd);
}

/** Gain linéaire du préampli : atténue du pire relèvement (plafonné), jamais de gain positif. */
export function computePreamp(sound: RadioSoundSettings): number {
  const cut = Math.min(PREAMP_MAX_CUT_DB, peakBoostDb(sound));
  return Math.pow(10, -cut / 20);
}

const LIMITER_ON: LimiterParams = { threshold: -3, knee: 2, ratio: 20, attack: 0.003, release: 0.15 };
// Compresseur transparent (ratio 1, seuil à 0 dB) : le nœud reste dans le graphe sans agir.
const LIMITER_OFF: LimiterParams = { threshold: 0, knee: 0, ratio: 1, attack: 0.003, release: 0.25 };

/**
 * Traduit des réglages en paramètres de chaque nœud du graphe. Son neutre (`enabled=false`) =
 * tous les filtres à 0 dB, préampli à 1, limiteur transparent : le graphe reste en place (pas de
 * reconnexion pendant la lecture), mais ne modifie rien.
 */
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
    // La protection n'agit QUE lorsque les réglages relèvent le son (risque d'écrêtage) : à plat, la
    // musique reste STRICTEMENT inchangée — sans quoi activer la radio compresserait les crêtes de
    // tous les morceaux, même sans aucun réglage d'égaliseur.
    limiter: active && sound.limiter && peakBoostDb(sound) > 0 ? LIMITER_ON : LIMITER_OFF,
  };
}
