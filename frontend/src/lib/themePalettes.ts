/**
 * Thèmes de l'interface : neuf couleurs, chacune en clair et en sombre. SOURCE UNIQUE des palettes (4 couleurs par
 * palette : fond, surface, accent, texte), relevées telles quelles du classeur de la refonte L7.
 *
 * Les jetons dérivés (`deriveTokens`) sont calculés ici, avec un contrôle de contraste, puis écrits dans
 * `src/app/themes.css` par `scripts/generate-themes.mjs`. Un test vérifie que le fichier CSS est à jour. La liste des
 * couleurs et le défaut sont repris côté serveur par `backend/app/utils/themes.py` (parité vérifiée par un test).
 * Module pur (aucun accès au DOM) : il est aussi chargé tel quel par le lanceur de tests Node, d'où les imports relatifs.
 */

export type ThemeId = "ardoise" | "chili" | "canary" | "rose-vif" | "charbon" | "orchidee" | "foret" | "ocean" | "pumpkin";
export type ThemeMode = "auto" | "light" | "dark";
export type ResolvedMode = "light" | "dark";

export interface Palette {
  bg: string;
  surface: string;
  accent: string;
  text: string;
}

export interface ThemeDef {
  id: ThemeId;
  labelKey: string;
  /** Couleur de base du thème (pastille du sélecteur). */
  base: string;
  light: Palette;
  dark: Palette;
}

export const DEFAULT_THEME: ThemeId = "ardoise";
export const DEFAULT_MODE: ThemeMode = "auto";
export const THEME_MODES: readonly ThemeMode[] = ["auto", "light", "dark"];

export const THEMES: readonly ThemeDef[] = [
  { id: "ardoise", labelKey: "settingsPage.themeArdoise", base: "#697485",
    light: { bg: "#ffffff", surface: "#e3ecf2", accent: "#697485", text: "#252d41" },
    dark: { bg: "#252d41", surface: "#536383", accent: "#e3ecf2", text: "#ffffff" } },
  { id: "chili", labelKey: "settingsPage.themeChili", base: "#972121",
    light: { bg: "#ffffff", surface: "#e2e2e2", accent: "#cd1c18", text: "#2e0605" },
    dark: { bg: "#2e0605", surface: "#440908", accent: "#e5211d", text: "#f6b7b5" } },
  { id: "canary", labelKey: "settingsPage.themeCanary", base: "#ffef00",
    light: { bg: "#ffffff", surface: "#fffab3", accent: "#e6d700", text: "#393500" },
    dark: { bg: "#393500", surface: "#555000", accent: "#ffef00", text: "#fffab3" } },
  { id: "rose-vif", labelKey: "settingsPage.themeRoseVif", base: "#ff2290",
    light: { bg: "#ffffff", surface: "#ffc2e0", accent: "#ff2290", text: "#6c0036" },
    dark: { bg: "#6c0036", surface: "#b5005a", accent: "#ff46a2", text: "#ffc2e0" } },
  { id: "charbon", labelKey: "settingsPage.themeCharbon", base: "#4a4a4a",
    light: { bg: "#ffffff", surface: "#e2e2e2", accent: "#333333", text: "#000000" },
    dark: { bg: "#000000", surface: "#353839", accent: "#4a4a4a", text: "#ffffff" } },
  { id: "orchidee", labelKey: "settingsPage.themeOrchidee", base: "#d51ece",
    light: { bg: "#ffffff", surface: "#ffd9fe", accent: "#d51ece", text: "#470a45" },
    dark: { bg: "#470a45", surface: "#6b0f67", accent: "#e85ce3", text: "#ffd9fe" } },
  { id: "foret", labelKey: "settingsPage.themeForet", base: "#2e6f40",
    light: { bg: "#ffffff", surface: "#cfffdc", accent: "#2e6f40", text: "#0a190e" },
    dark: { bg: "#14311c", surface: "#253d2c", accent: "#68ba7f", text: "#cfffdc" } },
  { id: "ocean", labelKey: "settingsPage.themeOcean", base: "#000080",
    light: { bg: "#ffffff", surface: "#9696ff", accent: "#000080", text: "#00001c" },
    dark: { bg: "#00001c", surface: "#0e0e55", accent: "#8080ff", text: "#ffffff" } },
  { id: "pumpkin", labelKey: "settingsPage.themePumpkin", base: "#ff7518",
    light: { bg: "#ffffff", surface: "#fff0e1", accent: "#ff7518", text: "#803600" },
    dark: { bg: "#5d2500", surface: "#9b3e00", accent: "#ffb98a", text: "#fff0e1" } },];

export const THEME_IDS: readonly ThemeId[] = THEMES.map((theme) => theme.id);

export function isThemeId(value: unknown): value is ThemeId {
  return typeof value === "string" && (THEME_IDS as readonly string[]).includes(value);
}

export function isThemeMode(value: unknown): value is ThemeMode {
  return value === "auto" || value === "light" || value === "dark";
}

/** Ancien thème (avant la 5.2) → couleur et mode les plus proches ; même table que `backend/app/utils/themes.py`. */
export const LEGACY_THEMES: Record<string, { theme: ThemeId; mode: ResolvedMode }> = {
  clair: { theme: "chili", mode: "light" },
  "charbon-sombre": { theme: "charbon", mode: "dark" },
  charbon: { theme: "charbon", mode: "light" },
  miel: { theme: "pumpkin", mode: "light" },
  menthe: { theme: "foret", mode: "light" },
  ciel: { theme: "ocean", mode: "light" },
  lavande: { theme: "orchidee", mode: "light" },
  beige: { theme: "ardoise", mode: "light" },
  coco: { theme: "pumpkin", mode: "light" },
  automne: { theme: "pumpkin", mode: "dark" },
  hiver: { theme: "ocean", mode: "dark" },
  lune: { theme: "ardoise", mode: "dark" },
  chili: { theme: "chili", mode: "dark" },
  orchidee: { theme: "orchidee", mode: "dark" },
  taupe: { theme: "canary", mode: "dark" },
};

export function paletteOf(theme: ThemeId, mode: ResolvedMode): Palette {
  const def = THEMES.find((t) => t.id === theme) ?? THEMES[0];
  return mode === "dark" ? def.dark : def.light;
}

// ---------------------------------------------------------------------------
// Couleurs et contrastes
// ---------------------------------------------------------------------------

type Rgb = [number, number, number];

export function hexToRgb(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

export function rgbToHex(rgb: Rgb): string {
  return "#" + rgb.map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, "0")).join("");
}

/** Mélange `from` → `to` : t = 0 donne `from`, t = 1 donne `to`. */
export function mix(from: string, to: string, t: number): string {
  const a = hexToRgb(from);
  const b = hexToRgb(to);
  return rgbToHex([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]);
}

function luminance(hex: string): number {
  const f = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Plus grand mélange de `from` vers `to` (jusqu'à `maxT`) qui garde `target` de contraste sur toutes les surfaces ;
 * `from` lui-même si même lui n'atteint pas la cible (la palette fournie ne permet rien de mieux).
 */
function farthestMix(from: string, to: string, surfaces: string[], target: number, maxT: number): string {
  let best = from;
  for (let step = 1; step <= 100; step++) {
    const t = (maxT * step) / 100;
    const candidate = mix(from, to, t);
    if (surfaces.every((surface) => contrast(candidate, surface) >= target)) best = candidate;
    else break;
  }
  return best;
}

/** Plus petit mélange de `from` vers `to` qui atteint `target` sur toutes les surfaces ; `to` si aucun n'y arrive. */
function nearestMix(from: string, to: string, surfaces: string[], target: number): string {
  for (let step = 0; step <= 100; step++) {
    const candidate = mix(from, to, step / 100);
    if (surfaces.every((surface) => contrast(candidate, surface) >= target)) return candidate;
  }
  return to;
}

export interface DerivedTokens {
  "bg-main": string;
  "bg-surface": string;
  "bg-surface-elevated": string;
  "bg-surface-hover": string;
  "text-main": string;
  "text-muted": string;
  "text-dim": string;
  "border-color": string;
  "border-focus": string;
  "accent-primary": string;
  "accent-primary-fg": string;
  "accent-text": string;
  "accent-sprint": string;
}

/**
 * Jetons d'un thème dans un mode. Les quatre couleurs de la palette sont reprises sans modification ; le reste en est
 * déduit : surfaces relevées vers le texte, textes secondaires rapprochés du fond tant que le contraste AA tient,
 * accent « texte » (liens, contours, anneaux) rapproché du texte jusqu'à AA quand l'accent pur est trop pâle ou trop
 * sombre, et couleur lisible posée sur l'accent plein.
 */
export function deriveTokens(palette: Palette, mode: ResolvedMode): DerivedTokens {
  const { bg, surface, accent, text } = palette;
  const elevated = mix(surface, text, mode === "dark" ? 0.08 : 0.05);
  const hover = mix(surface, text, mode === "dark" ? 0.14 : 0.1);
  const grounds = [bg, surface];
  const muted = farthestMix(text, bg, grounds, 5.5, 0.4);
  const dim = farthestMix(text, bg, grounds, 4.5, 0.6);
  const accentText = nearestMix(accent, text, [bg, surface, elevated], 4.5);
  const candidates = [text, bg, "#000000", "#ffffff"];
  const accentFg = candidates.find((c) => contrast(c, accent) >= 4.5) ?? candidates.sort((a, b) => contrast(b, accent) - contrast(a, accent))[0];
  return {
    "bg-main": bg,
    "bg-surface": surface,
    "bg-surface-elevated": elevated,
    "bg-surface-hover": hover,
    "text-main": text,
    "text-muted": muted,
    "text-dim": dim,
    "border-color": mix(bg, text, mode === "dark" ? 0.2 : 0.16),
    "border-focus": accentText,
    "accent-primary": accent,
    "accent-primary-fg": accentFg,
    "accent-text": accentText,
    // Repère « sprint » des programmes : jaune ambré lisible sur chaque mode.
    "accent-sprint": mode === "dark" ? "#ffb81c" : "#8a5a00",
  };
}

/** Mode effectif : `auto` suit le réglage du système (`prefersDark`). */
export function resolveMode(mode: ThemeMode, prefersDark: boolean): ResolvedMode {
  return mode === "auto" ? (prefersDark ? "dark" : "light") : mode;
}

/** Ancien nom → couleur + mode ; valeur inconnue → défaut. Même règle que `themes.resolve` côté serveur. */
export function resolveStored(theme: unknown, mode: unknown): { theme: ThemeId; mode: ThemeMode } {
  const legacy = typeof theme === "string" ? LEGACY_THEMES[theme] : undefined;
  if (legacy) return { theme: legacy.theme, mode: isThemeMode(mode) && mode !== DEFAULT_MODE ? mode : legacy.mode };
  return { theme: isThemeId(theme) ? theme : DEFAULT_THEME, mode: isThemeMode(mode) ? mode : DEFAULT_MODE };
}
