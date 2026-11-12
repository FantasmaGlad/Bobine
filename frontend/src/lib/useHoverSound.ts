"use client";

import { useCallback, useEffect, useRef } from "react";

export function useHoverSound(src: string, volume = 0.4) {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const audio = new Audio(src);
    audio.volume = volume;
    audioRef.current = audio;
    return () => {
      audioRef.current = null;
    };
  }, [src, volume]);

  return useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = 0;
    el.play().catch(() => {
    });
  }, []);
}
