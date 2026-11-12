"use client";

import { useEffect } from "react";
import { parseSafeMargin, safeMarginCss, SAFE_MARGIN_STORAGE_KEY } from "./screenSafe";

export function useScreenSafeMargin(enabled: boolean): void {
  useEffect(() => {
    const root = document.documentElement;
    if (!enabled) {
      root.style.removeProperty("--screen-safe-x");
      root.style.removeProperty("--screen-safe-y");
      return;
    }
    let percent: number | null = null;
    try {
      percent = parseSafeMargin(new URLSearchParams(window.location.search).get("safe"));
      if (percent !== null) {
        window.localStorage.setItem(SAFE_MARGIN_STORAGE_KEY, String(percent));
      } else {
        percent = parseSafeMargin(window.localStorage.getItem(SAFE_MARGIN_STORAGE_KEY));
      }
    } catch {
    }
    const css = safeMarginCss(percent ?? 0);
    root.style.setProperty("--screen-safe-x", css.x);
    root.style.setProperty("--screen-safe-y", css.y);
    return () => {
      root.style.removeProperty("--screen-safe-x");
      root.style.removeProperty("--screen-safe-y");
    };
  }, [enabled]);
}
