"use client";

import type { PlaybackState } from "@/lib/usePlaybackSocket";
import { useMediaClockFollower, type ClockTarget } from "@/lib/useMediaClockFollower";

interface VideoOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  state: PlaybackState;
  serverNow: () => number;
  tryPlay: (el: HTMLMediaElement | null | undefined) => void;
  onSeek?: () => void;
}

/** Cible « cours vidéo » : ancre `clock`, lecture/pause selon l'état partagé. */
export function selectVideoTarget(state: PlaybackState): ClockTarget {
  if (!state.current_video || (state.state !== "playing" && state.state !== "paused")) {
    return { anchor: null, mode: null };
  }
  return { anchor: state.clock, mode: state.state, key: state.current_video.id };
}

/** Fait suivre l'horloge serveur au <video> d'un écran (plan 4.0, P2-4). */
export function useVideoClockFollower({ videoRef, state, serverNow, tryPlay, onSeek }: VideoOptions) {
  useMediaClockFollower({ mediaRef: videoRef, state, select: selectVideoTarget, serverNow, tryPlay, onSeek });
}
