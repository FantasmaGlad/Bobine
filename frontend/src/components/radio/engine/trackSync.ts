import type { RadioAnnouncementInfo } from "@/lib/useRadioSocket";
import type { DuckSettings } from "./announcements";

export type Slot = 0 | 1;
export type TrackDecision = "unload" | "same" | "promote" | "load";
export type TransportAction = "play" | "pause" | "none";

export interface Decks {
  active: Slot;
  trackIds: [number | null, number | null];
  crossfading: boolean;
}

export const otherSlot = (slot: Slot): Slot => (slot === 0 ? 1 : 0);

export function decideTrack(trackId: number | null, decks: Decks): TrackDecision {
  if (trackId === null) return "unload";
  if (trackId === decks.trackIds[decks.active]) return "same";
  if (decks.crossfading && decks.trackIds[otherSlot(decks.active)] === trackId) return "promote";
  return "load";
}

export function targetGain(decision: TrackDecision, ducking: boolean, volume: number, duck: DuckSettings): number | null {
  if (decision === "same") return ducking ? null : volume / 100;
  if (decision === "promote" || decision === "load") return (ducking ? duck.level : volume) / 100;
  return null;
}

export function transportAction(
  cause: string,
  announcement: Pick<RadioAnnouncementInfo, "mode"> | null,
  playing: boolean,
  paused: boolean,
): { seek: boolean; action: TransportAction } {
  const seek = cause === "radio_seek" || cause === "radio_restart_track";
  if (announcement?.mode === "wait_end") return { seek, action: "none" };
  if (playing && paused) return { seek, action: "play" };
  if (!playing && !paused) return { seek, action: "pause" };
  return { seek, action: "none" };
}
