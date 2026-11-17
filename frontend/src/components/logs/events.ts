import type { Language } from "@/lib/i18n";

export interface ActivityLogEntry {
  id: number;
  timestamp: string;
  event_type: string;
  detail: string | null;
}

const LABELLED_EVENTS = new Set([
  "video_imported",
  "background_imported",
  "audio_course_imported",
  "video_started",
  "background_started",
  "audio_course_started",
  "playlist_started",
  "playback_stopped",
  "playlist_created",
  "playlist_updated",
  "playlist_deleted",
  "schedule_created",
  "schedule_updated",
  "schedule_deleted",
  "schedule_override_created",
]);

export function eventTypeLabel(type: string, t: (key: string) => string): string {
  return LABELLED_EVENTS.has(type) ? t(`logs.eventLabels.${type}`) : type;
}

export function formatTimestamp(iso: string, language: Language) {
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return d.toLocaleString(language === "fr" ? "fr-FR" : "en-US", { dateStyle: "short", timeStyle: "medium" });
}
