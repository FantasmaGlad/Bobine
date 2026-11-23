import type { DisplayChannel } from "./displayChannel.ts";

export interface SignageEntry {
  visual_id: number;
  seconds: number | null;
  title: string;
  is_image: boolean;
  play_seconds: number | null;
  duration_seconds: number | null;
}

export interface SignageLoop {
  channel: DisplayChannel;
  items: SignageEntry[];
}

export const SIGNAGE_MIN_SECONDS = 2;
export const SIGNAGE_MAX_SECONDS = 3600;

export function entryDurationMs(entry: SignageEntry): number | null {
  return entry.play_seconds === null ? null : entry.play_seconds * 1000;
}

export interface SlotPlan {
  holdMs: number | null;
  loop: boolean;
  advances: boolean;
}

export function planSlot(entry: SignageEntry, alone: boolean): SlotPlan {
  const holdMs = entryDurationMs(entry);
  if (alone) return { holdMs: null, loop: true, advances: false };
  return { holdMs, loop: !entry.is_image && holdMs !== null, advances: true };
}

export function nextIndex(index: number, length: number): number {
  return length === 0 ? 0 : (index + 1) % length;
}

export function moved<T>(items: readonly T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length || from === to) return [...items];
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function clampSeconds(raw: string): number | null {
  if (raw.trim() === "") return null;
  const value = Math.round(Number(raw));
  if (!Number.isFinite(value)) return null;
  return Math.min(SIGNAGE_MAX_SECONDS, Math.max(SIGNAGE_MIN_SECONDS, value));
}

export function streamPath(visualId: number): string {
  return `/visuals/${visualId}/stream`;
}
