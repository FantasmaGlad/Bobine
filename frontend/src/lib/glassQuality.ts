/**
 * Qualité du verre : l'échelle de flou (`--blur-scale`, voir globals.css) s'adapte au matériel au lieu d'être figée.
 * Mode « auto » : on mesure la fluidité pendant le défilement et on descend d'un palier si l'appareil ne suit pas ;
 * le palier retenu est mémorisé (jamais de remontée automatique, pour ne pas osciller). Les autres modes sont un choix
 * explicite de l'utilisateur. Le réglage système « transparence réduite » reste prioritaire (voir `applyScale`).
 */

export type GlassMode = "auto" | "full" | "reduced" | "off";

/** Paliers d'échelle de flou : complet, réduit, supprimé. */
export const GLASS_STEPS = [1, 0.5, 0] as const;

/** En deçà de ~40 images par seconde (au 75e centile), le palier suivant est choisi. */
const SLOW_FRAME_MS = 24;
/** Nombre d'images mesurées avant de décider. */
export const MIN_SAMPLE = 45;

export const MODE_KEY = "bobine.glass.mode";
export const STEP_KEY = "bobine.glass.step";
export const MODE_EVENT = "bobine:glass-mode";

export function isGlassMode(value: unknown): value is GlassMode {
  return value === "auto" || value === "full" || value === "reduced" || value === "off";
}

/** Échelle de flou pour un mode ; `autoStep` n'est lu qu'en mode auto. */
export function scaleForMode(mode: GlassMode, autoStep: number): number {
  if (mode === "full") return GLASS_STEPS[0];
  if (mode === "reduced") return GLASS_STEPS[1];
  if (mode === "off") return GLASS_STEPS[2];
  return GLASS_STEPS[Math.min(Math.max(0, Math.trunc(autoStep) || 0), GLASS_STEPS.length - 1)];
}

/** Palier suivant selon les durées d'image (ms) relevées au défilement ; inchangé si l'échantillon est trop court. */
export function nextStep(frameDeltasMs: number[], step: number): number {
  const last = GLASS_STEPS.length - 1;
  if (step >= last || frameDeltasMs.length < MIN_SAMPLE) return step;
  const sorted = [...frameDeltasMs].sort((a, b) => a - b);
  const p75 = sorted[Math.floor(sorted.length * 0.75)];
  return p75 > SLOW_FRAME_MS ? step + 1 : step;
}

/** Pose l'échelle sur la page, sauf si le système demande déjà moins de transparence (la règle CSS prime alors). */
export function applyScale(scale: number): void {
  if (typeof document === "undefined") return;
  if (window.matchMedia?.("(prefers-reduced-transparency: reduce)").matches) {
    document.documentElement.style.removeProperty("--blur-scale");
    return;
  }
  document.documentElement.style.setProperty("--blur-scale", String(scale));
}

function read(key: string): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function write(key: string, value: string): void {
  try { window.localStorage.setItem(key, value); } catch { /* stockage indisponible : réglage de la session seulement */ }
}

export function loadMode(): GlassMode {
  const saved = read(MODE_KEY);
  return isGlassMode(saved) ? saved : "auto";
}
export function saveMode(mode: GlassMode): void {
  write(MODE_KEY, mode);
  window.dispatchEvent(new Event(MODE_EVENT));
}
export function loadStep(): number {
  const n = Number(read(STEP_KEY));
  return Number.isInteger(n) && n >= 0 && n < GLASS_STEPS.length ? n : 0;
}
export function saveStep(step: number): void {
  write(STEP_KEY, String(step));
}
