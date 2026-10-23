import type { ApiError } from "@/lib/devicesApi";
import { formatBytes } from "@/lib/storageApi";
import type { Notify } from "@/components/devices/common";

export type T = (key: string, params?: Record<string, string | number>) => string;
export type Lang = "fr" | "en";

export interface StorageCtx {
  t: T;
  lang: Lang;
  notify: Notify;
}

/** Message lisible d'une erreur d'API : texte propre au stockage, puis texte des périphériques (PIN...), puis message du serveur. */
export function storageErrorText(error: ApiError, t: T, lang: Lang = "fr"): string {
  const own = `storage.errors.${error.code}`;
  const params: Record<string, string | number> = {};
  if (typeof error.extra.needed_bytes === "number") params.needed = formatBytes(error.extra.needed_bytes, lang);
  if (typeof error.extra.free_bytes === "number") params.free = formatBytes(error.extra.free_bytes, lang);
  const translated = t(own, params);
  if (translated !== own) return translated;
  const shared = `devices.errors.${error.code}`;
  const sharedText = t(shared);
  if (sharedText !== shared) return sharedText;
  return error.message || t("storage.errors.generic");
}

/** Traduction avec repli : la clé, sinon `fallback` (code inconnu du serveur plus récent que le client). */
export function tr(t: T, key: string, fallback = "", params?: Record<string, string | number>): string {
  const text = t(key, params);
  return text === key ? fallback : text;
}
