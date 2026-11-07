/**
 * Bornes des réglages numériques de lecture. Miroir de `SETTING_BOUNDS` dans `backend/app/api_contract.py` : le serveur
 * refuse hors de ces bornes, `backend/tests/test_setting_bounds.py` vérifie que les deux listes sont identiques.
 */
export type TimingSettingKey = "wait_time_between_courses" | "volume_default" | "audio_chain_timer_seconds" | "radio_announcement_fade_ms";

export const SETTING_BOUNDS: Record<TimingSettingKey, { min: number; max: number; unit: "s" | "%" | "ms" }> = {
  wait_time_between_courses: { min: 0, max: 3600, unit: "s" },
  volume_default: { min: 0, max: 100, unit: "%" },
  audio_chain_timer_seconds: { min: 0, max: 86400, unit: "s" },
  radio_announcement_fade_ms: { min: 0, max: 10000, unit: "ms" },
};

export const TIMING_SETTING_KEYS = Object.keys(SETTING_BOUNDS) as TimingSettingKey[];

/** Valeur saisie → entier dans les bornes, ou null si elle n'est pas un nombre entier de la plage. */
export function parseBounded(key: TimingSettingKey, text: string): number | null {
  if (!/^\d+$/.test(text.trim())) return null;
  const value = Number(text);
  const { min, max } = SETTING_BOUNDS[key];
  return value >= min && value <= max ? value : null;
}
