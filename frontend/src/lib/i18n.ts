import { dictionary } from "@bobine/dictionary";
import { translateIn, translateListIn, type Language } from "@/lib/i18n/core";

export type { Language } from "@/lib/i18n/core";

export const UI_LANGUAGE: Language = process.env.NEXT_PUBLIC_BOBINE_LANG === "en" ? "en" : "fr";

export function translate(key: string, params?: Record<string, string | number>): string {
  return translateIn(dictionary, key, params);
}

export function translateList(key: string): string[] {
  return translateListIn(dictionary, key);
}
