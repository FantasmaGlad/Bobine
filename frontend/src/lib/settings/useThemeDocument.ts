import { useEffect, useState } from "react";
import type { Language } from "@/lib/i18n";
import { pushThemeToNative } from "@/lib/nativeBridge";
import { applyChannelFavicon, type UpdateChannel } from "@/lib/releaseChannel";
import { resolveMode, type ResolvedMode, type ThemeId, type ThemeMode } from "@/lib/themePalettes";

export function useThemeDocument(theme: ThemeId, themeMode: ThemeMode, language: Language, updateChannel: UpdateChannel): ResolvedMode {
  const [resolvedMode, setResolvedMode] = useState<ResolvedMode>("light");

  useEffect(() => {
    const query = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    const apply = () => {
      const resolved = resolveMode(themeMode, Boolean(query?.matches));
      document.documentElement.setAttribute("data-mode", resolved);
      setResolvedMode(resolved);
    };
    apply();
    if (themeMode !== "auto" || !query) return;
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, [themeMode]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("olc-theme", theme);
      localStorage.setItem("olc-theme-mode", themeMode);
    } catch {
    }
    const frame = requestAnimationFrame(() => requestAnimationFrame(pushThemeToNative));
    return () => cancelAnimationFrame(frame);
  }, [theme, themeMode, resolvedMode]);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  useEffect(() => {
    applyChannelFavicon(document, updateChannel);
  }, [updateChannel]);

  return resolvedMode;
}
