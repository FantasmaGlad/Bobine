/**
 * Marge de sécurité d'un écran de diffusion (overscan des téléviseurs).
 *
 * Beaucoup de téléviseurs « zooment » l'image de 2 à 5 % et rognent les bords : titres,
 * horloge et boutons se retrouvent coupés. La marge se règle PAR APPAREIL (chaque téléviseur
 * est différent) avec le paramètre d'URL `?safe=<0-10>` (pourcentage de la largeur et de la
 * hauteur laissé libre de chaque côté), mémorisé ensuite dans le navigateur de l'écran.
 * `?safe=0` la supprime. Logique PURE, testable (`frontend/tests/`).
 */
export const SAFE_MARGIN_STORAGE_KEY = "bobine.screenSafeMargin";
export const SAFE_MARGIN_MAX = 10;

/** Convertit une valeur brute (URL ou stockage) en pourcentage borné, ou null si invalide. */
export function parseSafeMargin(raw: string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const trimmed = raw.trim().replace(",", ".");
  if (trimmed === "") return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return null;
  return Math.min(SAFE_MARGIN_MAX, Math.max(0, Math.round(value * 10) / 10));
}

/** Valeurs CSS des variables `--screen-safe-x` / `--screen-safe-y` pour un pourcentage donné. */
export function safeMarginCss(percent: number): { x: string; y: string } {
  const p = Math.min(SAFE_MARGIN_MAX, Math.max(0, percent));
  return { x: `${p}vw`, y: `${p}vh` };
}
