import { getApiUrl } from "./apiUrl.ts";

/** Cours tel que le présentent les écrans de sélection (`/cinema`, `/grid`). */
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

/** Adresse de la vignette d'un cours, ou `null` s'il n'en a pas. */
export function thumbnailUrl(video: CinemaVideo): string | null {
  const path = video.thumbnail_path || video.thumbnail_url;
  if (!path) return null;
  const filename = path.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}
