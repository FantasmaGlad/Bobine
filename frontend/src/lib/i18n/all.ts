import { dictionary as en } from "./en.ts";
import { dictionary as fr } from "./fr.ts";
import { translateIn, translateListIn, type Dict, type Language } from "./core.ts";

export type { Dict, Language } from "./core.ts";

/** Les deux langues ensemble : réservé aux tests (le code de l'application n'embarque qu'une langue). */
export const dictionaries: Record<Language, Dict> = { fr, en };

export function translate(language: Language, key: string, params?: Record<string, string | number>): string {
  return translateIn(dictionaries[language], key, params);
}

export function translateList(language: Language, key: string): string[] {
  return translateListIn(dictionaries[language], key);
}
