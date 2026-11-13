"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TICK_MS = 250;
const STALE_MS = 8000;
const SEEK_HOLD_MS = 2000;

interface Seek {
  position: number;
  timestamp: number;
}

interface RemoteCinema {
  title?: string | null;
  playing?: boolean;
  position_seconds?: number;
  duration_seconds?: number;
}

type Live<T> = T & { playing: boolean; position_seconds: number };

type Send = (command: string, params?: Record<string, unknown>) => void;

export function useNowPlaying<T extends RemoteCinema>(cinemaState: T | null | undefined, sendCommand: Send, smooth = false) {
  const [nowPlaying, setNowPlaying] = useState<Live<T> | null>(null);
  const stateRef = useRef(cinemaState);
  const receivedAtRef = useRef(0);
  const pendingRef = useRef<boolean | null>(null);
  const seekRef = useRef<Seek | null>(null);
  const seekTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const smoothedRef = useRef(0);
  const lastTickRef = useRef(0);
  const viewRef = useRef<Live<T> | null>(null);

  const tick = useCallback(() => {
    const now = Date.now();
    const report = stateRef.current;
    const raw = report && report.title && now - receivedAtRef.current < STALE_MS ? report : null;
    const playing = pendingRef.current ?? raw?.playing ?? false;
    const seek = seekRef.current;
    const duration = raw?.duration_seconds || Infinity;
    const dt = Math.max(0, Math.min(1, (now - lastTickRef.current) / 1000));
    lastTickRef.current = now;
    let position = 0;
    if (!raw) {
      smoothedRef.current = 0;
    } else if (seek) {
      position = Math.min(duration, seek.position + (playing ? Math.max(0, (now - seek.timestamp) / 1000) : 0));
      smoothedRef.current = position;
    } else {
      const base = raw.position_seconds ?? 0;
      const reported = Math.min(duration, base + (raw.playing ? Math.max(0, (now - receivedAtRef.current) / 1000) : 0));
      if (smooth && !playing) {
        position = base;
      } else if (smooth) {
        const expected = smoothedRef.current + dt;
        position = Math.min(duration, Math.abs(expected - reported) >= 2.5 ? reported : Math.max(expected, reported - 0.5));
      } else {
        position = reported;
      }
      smoothedRef.current = position;
    }
    viewRef.current = raw ? { ...raw, playing, position_seconds: position } : null;
    setNowPlaying(viewRef.current);
  }, [smooth]);

  useEffect(() => {
    const now = Date.now();
    stateRef.current = cinemaState;
    receivedAtRef.current = now;
    pendingRef.current = null;
    const seek = seekRef.current;
    if (seek) {
      const elapsed = (now - seek.timestamp) / 1000;
      const expected = seek.position + (cinemaState?.playing ? elapsed : 0);
      if (Math.abs((cinemaState?.position_seconds ?? 0) - expected) < 2.5 || elapsed > 1.2) seekRef.current = null;
    }
    const id = setTimeout(tick, 0);
    return () => clearTimeout(id);
  }, [cinemaState, tick]);

  useEffect(() => {
    const id = setInterval(tick, TICK_MS);
    return () => {
      clearInterval(id);
      if (seekTimerRef.current) clearTimeout(seekTimerRef.current);
    };
  }, [tick]);

  const holdSeek = useCallback((position: number) => {
    seekRef.current = { position, timestamp: Date.now() };
    if (seekTimerRef.current) clearTimeout(seekTimerRef.current);
    seekTimerRef.current = setTimeout(() => {
      seekRef.current = null;
    }, SEEK_HOLD_MS);
    sendCommand("cinema_command", { action: "seek", position_seconds: position });
    tick();
  }, [sendCommand, tick]);

  const playPause = useCallback(() => {
    const view = viewRef.current;
    if (!view) return;
    pendingRef.current = !view.playing;
    sendCommand("cinema_command", { action: pendingRef.current ? "play" : "pause" });
    tick();
  }, [sendCommand, tick]);

  const seekDelta = useCallback((delta: number) => {
    const view = viewRef.current;
    if (!view) return;
    const base = seekRef.current ? seekRef.current.position : view.position_seconds;
    holdSeek(Math.max(0, Math.min(base + delta, view.duration_seconds || Infinity)));
  }, [holdSeek]);

  const stop = useCallback(() => {
    sendCommand("cinema_command", { action: "stop" });
    pendingRef.current = null;
    seekRef.current = null;
  }, [sendCommand]);

  return { nowPlaying, playPause, seekDelta, commitSeek: holdSeek, stop };
}

export type NowPlaying<T extends RemoteCinema = RemoteCinema> = ReturnType<typeof useNowPlaying<T>>;
