"use client";

import { useEffect, useRef, useState } from "react";

import { useTicker } from "./useCinemaVideos";

interface RemoteCinema {
  title?: string | null;
  playing?: boolean;
  position_seconds?: number;
  duration_seconds?: number;
}

type Send = (type: string, payload: Record<string, unknown>) => void;

const STALE_MS = 8000;

function extrapolate(base: number, since: number, now: number, playing: boolean, duration: number | undefined): number {
  return Math.min(duration || Infinity, base + (playing ? Math.max(0, (now - since) / 1000) : 0));
}

export function useNowPlaying<T extends RemoteCinema>(cinemaState: T | null | undefined, sendCommand: Send) {
  const tick = useTicker(250);
  const receivedAt = useRef(0);
  const [pendingPlaying, setPendingPlaying] = useState<boolean | null>(null);
  const [optimisticSeek, setOptimisticSeek] = useState<{ position: number; timestamp: number } | null>(null);

  useEffect(() => {
    receivedAt.current = Date.now();
    setPendingPlaying(null);
    setOptimisticSeek((current) => {
      if (!current) return null;
      const elapsed = (Date.now() - current.timestamp) / 1000;
      const expected = current.position + (cinemaState?.playing ? elapsed : 0);
      return Math.abs((cinemaState?.position_seconds ?? 0) - expected) < 2.5 || elapsed > 1.2 ? null : current;
    });
  }, [cinemaState]);

  const raw = cinemaState && cinemaState.title && tick - receivedAt.current < STALE_MS ? cinemaState : null;
  const playing = pendingPlaying ?? raw?.playing ?? false;
  const position = optimisticSeek
    ? extrapolate(optimisticSeek.position, optimisticSeek.timestamp, tick, playing, raw?.duration_seconds)
    : raw ? extrapolate(raw.position_seconds ?? 0, receivedAt.current, tick, !!raw.playing, raw.duration_seconds) : 0;
  const nowPlaying = raw ? { ...raw, playing, position_seconds: position } : null;

  const playPause = () => {
    if (!nowPlaying) return;
    setPendingPlaying(!nowPlaying.playing);
    sendCommand("cinema_command", { action: nowPlaying.playing ? "pause" : "play" });
  };

  const seekDelta = (delta: number) => {
    if (!nowPlaying) return;
    const base = optimisticSeek ? optimisticSeek.position : nowPlaying.position_seconds;
    const target = Math.max(0, Math.min(base + delta, nowPlaying.duration_seconds || Infinity));
    setOptimisticSeek({ position: target, timestamp: Date.now() });
    sendCommand("cinema_command", { action: "seek", position_seconds: target });
  };

  const stop = () => {
    sendCommand("cinema_command", { action: "stop" });
    setPendingPlaying(null);
    setOptimisticSeek(null);
  };

  return { nowPlaying, playPause, seekDelta, stop };
}

export type NowPlaying<T extends RemoteCinema = RemoteCinema> = ReturnType<typeof useNowPlaying<T>>;
