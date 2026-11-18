import { thumbnailUrl as thumbnailFromPath } from "./thumbnail.ts";

export interface CinemaVideo {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
  thumbnail_url?: string | null;
  width?: number | null;
  height?: number | null;
  codec?: string | null;
  description?: string | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
  fps?: number | null;
  bitrate_kbps?: number | null;
}

export function thumbnailUrl(video: CinemaVideo): string | null {
  return thumbnailFromPath(video.thumbnail_path || video.thumbnail_url);
}
