import { getApiUrl } from "@/lib/apiUrl";

export interface VideoSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path?: string | null;
  description?: string | null;
  width?: number | null;
  height?: number | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
}

export interface PlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
  thumbnail_path?: string | null;
}

export interface OccurrenceSummary {
  schedule_id: number;
  run_at: string;
  title: string | null;
  program: string | null;
  override_action: string | null;
}

export interface BackgroundSummary {
  id: number;
  title: string;
  duration_seconds?: number | null;
  thumbnail_path?: string | null;
  file_path?: string;
  is_image?: boolean;
}

export interface InterruptedState {
  id: number;
  cause: string | null;
  interrupted_at: string;
  video_id?: number | null;
  title?: string | null;
  position_seconds?: number | null;
  target_type?: string | null;
  target_id?: number | null;
}

export type Send = (command: string, params?: Record<string, unknown>) => void;

export function thumbnailOf(path: string | null | undefined): string | null {
  const filename = path?.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

export const THUMB_STYLE = { width: "88px", height: "50px", objectFit: "cover", borderRadius: "var(--radius-sm)", flexShrink: 0, background: "var(--bg-surface-elevated)" } as const;
