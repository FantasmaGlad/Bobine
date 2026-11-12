import type { Language } from "./i18n.ts";
import type { ScheduleChannel } from "./scheduleChannels.ts";

export type TargetType = "video" | "playlist" | "radio_playlist";
export type ScheduleTypeValue = "once" | "recurring";
export type OverrideActionValue = "cancelled" | "replaced";
export type ChannelValue = ScheduleChannel;

export interface VideoSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
}

export interface PlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
  thumbnail_path: string | null;
}

export interface RadioPlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
  cover_track_id?: number | null;
  is_default?: boolean;
}

export interface ScheduleDetail {
  id: number;
  target_type: TargetType;
  target_id: number;
  target_title: string | null;
  target_program: string | null;
  schedule_type: ScheduleTypeValue;
  run_at: string | null;
  days_of_week: number[] | null;
  time_of_day: string | null;
  active: boolean;
  override_count: number;
  end_time: string | null;
  is_24_7: boolean;
}

export interface Occurrence {
  schedule_id: number;
  schedule_type: ScheduleTypeValue;
  run_at: string;
  target_type: TargetType;
  target_id: number;
  title: string | null;
  program: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
  cover_track_id: number | null;
  end_time: string | null;
  is_24_7: boolean;
  is_override: boolean;
  override_action: OverrideActionValue | null;
  override_id: number | null;
}

export function getWeekStart(source: Date): Date {
  const d = new Date(source);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return d;
}

export function addDays(source: Date, days: number): Date {
  const d = new Date(source);
  d.setDate(d.getDate() + days);
  return d;
}

export function isSameLocalDay(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

export function toDatetimeLocalValue(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function toOccurrenceDateString(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function formatWeekLabel(weekStart: Date, language: Language) {
  const weekEnd = addDays(weekStart, 6);
  const locale = language === "fr" ? "fr-FR" : "en-US";
  const fmt = (d: Date) => d.toLocaleDateString(locale, { day: "numeric", month: "short" });
  return `${fmt(weekStart)} — ${fmt(weekEnd)}`;
}

export function formatOccurrenceTime(iso: string) {
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

export function occurrenceKey(o: Occurrence): string {
  return `${o.schedule_id}-${o.run_at}`;
}

export function minutesToHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60) % 24;
  const m = Math.round(minutes % 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

export const MIN_BLOCK_MINUTES = 15;
export const MINUTES_PER_DAY = 1440;

export function minutesSinceMidnight(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

export function parseTimeToMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map((n) => parseInt(n, 10));
  return h * 60 + m;
}

interface OccurrenceWindow {
  startMin: number;
  durationMin: number;
  isBackgroundBand: boolean;
}

export function getOccurrenceWindow(o: Occurrence): OccurrenceWindow {
  const startMin = minutesSinceMidnight(o.run_at);
  if (o.target_type === "radio_playlist") {
    if (o.is_24_7) {
      return { startMin: 0, durationMin: MINUTES_PER_DAY, isBackgroundBand: true };
    }
    if (o.end_time) {
      const endMin = parseTimeToMinutes(o.end_time);
      const durationMin = endMin > startMin ? endMin - startMin : MIN_BLOCK_MINUTES;
      return { startMin, durationMin, isBackgroundBand: false };
    }
    return { startMin, durationMin: MIN_BLOCK_MINUTES, isBackgroundBand: false };
  }
  const durationMin = o.duration_seconds ? Math.max(o.duration_seconds / 60, MIN_BLOCK_MINUTES) : MIN_BLOCK_MINUTES;
  return { startMin, durationMin, isBackgroundBand: false };
}

export function computeCutsPrevious(dayOccurrences: Occurrence[]): Set<string> {
  const cuts = new Set<string>();
  let activeEndMin = -1;
  for (const o of dayOccurrences) {
    const win = getOccurrenceWindow(o);
    if (win.isBackgroundBand) continue;
    if (win.startMin < activeEndMin) cuts.add(occurrenceKey(o));
    activeEndMin = win.startMin + win.durationMin;
  }
  return cuts;
}
