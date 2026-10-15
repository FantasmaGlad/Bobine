"use client";

import type { PlaybackState } from "@/lib/usePlaybackSocket";
import { useMediaClockFollower, type ClockTarget } from "@/lib/useMediaClockFollower";

interface AudioOptions {
  audioRef: React.RefObject<HTMLAudioElement | null>;
  state: PlaybackState;
  serverNow: () => number;
  tryPlay: (el: HTMLMediaElement | null | undefined) => void;
  onSeek?: () => void;
}

/** Cible « piste audio du mode coach » : ancre `audio_clock`, lecture/pause selon `audio_playing`. */
export function selectAudioTarget(state: PlaybackState): ClockTarget {
  if (!state.current_audio_course || state.state !== "coach_mode" || state.audio_track_index === null) {
    return { anchor: null, mode: null };
  }
  const track = state.audio_tracks?.[state.audio_track_index];
  return {
    anchor: state.audio_clock,
    mode: state.audio_playing ? "playing" : "paused",
    key: track ? track.id : null,
  };
}

/** Fait suivre l'horloge serveur à l'<audio> du mode coach. */
export function useAudioClockFollower({ audioRef, state, serverNow, tryPlay, onSeek }: AudioOptions) {
  useMediaClockFollower({ mediaRef: audioRef, state, select: selectAudioTarget, serverNow, tryPlay, onSeek });
}
