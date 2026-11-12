"use client";

import { useEffect } from "react";

export function useAutoFullscreen(enabled: boolean) {
  useEffect(() => {
    if (!enabled || typeof document === "undefined") return;

    const tryFullscreen = () => {
      const el = document.documentElement;
      const isFullscreen = document.fullscreenElement != null;
      if (!isFullscreen && el.requestFullscreen) {
        el.requestFullscreen().catch(() => {
        });
      }
      document.removeEventListener("touchend", tryFullscreen);
      document.removeEventListener("click", tryFullscreen);
    };

    document.addEventListener("touchend", tryFullscreen, { once: true });
    document.addEventListener("click", tryFullscreen, { once: true });

    return () => {
      document.removeEventListener("touchend", tryFullscreen);
      document.removeEventListener("click", tryFullscreen);
    };
  }, [enabled]);
}
