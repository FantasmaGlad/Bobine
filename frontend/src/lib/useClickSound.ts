"use client";

import { useEffect, useRef } from "react";

const CLICK_SOUND_SRC = "/sounds/clic.mp3";
const INTERACTIVE_SELECTOR = 'button, a, [role="button"], input[type="button"], input[type="submit"], select';

export function useClickSound(enabled: boolean) {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    const audio = new Audio(CLICK_SOUND_SRC);
    audio.volume = 0.5;
    audioRef.current = audio;

    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target || !target.closest(INTERACTIVE_SELECTOR)) return;
      const el = audioRef.current;
      if (!el) return;
      el.currentTime = 0;
      el.play().catch(() => {
      });
    };

    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      audioRef.current = null;
    };
  }, [enabled]);
}
