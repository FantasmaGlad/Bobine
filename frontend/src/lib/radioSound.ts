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
