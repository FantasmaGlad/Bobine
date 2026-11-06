import { dictionary } from "@bobine/dictionary";
import { translateIn, translateListIn, type Language } from "@/lib/i18n/core";

export type { Language } from "@/lib/i18n/core";

/**
 * Langue embarquée dans cet export statique. `npm run build` produit un export par langue
 * (scripts/build.mjs) et le backend sert celui de la langue enregistrée : un écran ne charge que ses textes.
 * `@bobine/dictionary` est résolu vers fr.ts ou en.ts à la compilation (next.config.ts).
 */
export const UI_LANGUAGE: Language = process.env.NEXT_PUBLIC_BOBINE_LANG === "en" ? "en" : "fr";

export function translate(key: string, params?: Record<string, string | number>): string {
  return translateIn(dictionary, key, params);
}

export function translateList(key: string): string[] {
  return translateListIn(dictionary, key);
}
