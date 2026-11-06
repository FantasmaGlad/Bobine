export type Language = "fr" | "en";

export type Dict = { [key: string]: string | string[] | Dict };

export const LANGUAGES: Language[] = ["fr", "en"];

// Toute chaîne affichée à l'utilisateur passe par un dictionnaire (fr.ts, en.ts) plutôt que d'être codée en dur
// dans les composants. Organisé par section d'écran plutôt qu'un plat unique, pour rester navigable malgré le volume.
function lookup(dict: Dict, path: string[]): string | string[] | undefined {
  let node: Dict | string | string[] = dict;
  for (const part of path) {
    if (typeof node === "string" || Array.isArray(node) || node === undefined) return undefined;
    node = node[part];
  }
  return typeof node === "string" || Array.isArray(node) ? node : undefined;
}

export function lookupPath(dict: Dict, key: string): string | string[] | undefined {
  return lookup(dict, key.split("."));
}

/**
 * Résout une clé pointée ("nav.dashboard") dans `dict`, avec interpolation `{{param}}` simple. Une clé absente
 * renvoie la clé brute, pour repérer un oubli plutôt que planter silencieusement (tests/i18nParity.test.ts garantit
 * que les deux langues ont exactement les mêmes clés).
 */
export function translateIn(dict: Dict, key: string, params?: Record<string, string | number>): string {
  const value = lookupPath(dict, key);
  if (value === undefined || Array.isArray(value)) return key;
  if (!params) return value;
  return value.replace(/\{\{(\w+)\}\}/g, (_, name) => String(params[name] ?? ""));
}

/** Variante de translateIn() pour les clés dont la valeur est une liste (noms de jours, par exemple). */
export function translateListIn(dict: Dict, key: string): string[] {
  const value = lookupPath(dict, key);
  return Array.isArray(value) ? value : [];
}
