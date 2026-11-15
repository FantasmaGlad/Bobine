import type { RadioRepeatMode } from "@/lib/useRadioSocket";

export interface CrossfadeState<T> {
  order: T[];
  index: number | null;
  repeat: RadioRepeatMode;
  crossfade_seconds: number;
}

export interface CrossfadeFlags {
  crossfading: boolean;
  graphReady: boolean;
  announcing: boolean;
}

export function crossfadeSeconds(state: { crossfade_seconds: number }) {
  return Math.max(0, state.crossfade_seconds || 0);
}

export function crossfadeDurationMs(seconds: number) {
  return Math.max(200, seconds * 1000);
}

export function crossfadeTarget<T>(
  state: CrossfadeState<T>,
  el: { duration: number; currentTime: number },
  flags: CrossfadeFlags,
): T | null {
  if (flags.crossfading || !flags.graphReady || flags.announcing) return null;
  if (state.repeat === "track") return null;
  const { duration, currentTime } = el;
  if (!isFinite(duration) || duration <= 0) return null;
  const seconds = crossfadeSeconds(state);
  if (seconds <= 0 || duration - currentTime > seconds) return null;
  const { order, index } = state;
  if (index === null) return null;
  if (index + 1 < order.length) return order[index + 1];
  if (state.repeat === "playlist" && order.length > 0) return order[0];
  return null;
}
