import { getApiUrl } from "@/lib/apiUrl";
import { MIN_BLOCK_MINUTES, type Occurrence, type TargetType } from "@/lib/scheduleTime";

export interface DragPayload {
  type: TargetType;
  id: number;
  durationMinutes: number;
  label: string;
}

export function thumbnailSrc(path: string | null): string | null {
  const filename = path?.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

export function coverSrc(trackId: number | null | undefined): string | null {
  return trackId != null ? getApiUrl(`/radio/tracks/${trackId}/cover`) : null;
}

export function occurrenceThumb(o: Occurrence): string | null {
  return o.target_type === "radio_playlist" ? coverSrc(o.cover_track_id) : thumbnailSrc(o.thumbnail_path);
}

export function blockMinutes(seconds: number | null | undefined): number {
  return seconds ? Math.max(seconds / 60, MIN_BLOCK_MINUTES) : MIN_BLOCK_MINUTES;
}

export function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export const hourLabel = (hour: number) => `${hour.toString().padStart(2, "0")}:00`;
