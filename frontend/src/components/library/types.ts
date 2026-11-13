import type { PendingUploadSpec } from "@/lib/UploadManager";

export interface VideoSubtitleItem {
  id: number;
  video_id: number;
  language_code: string;
  language_label: string;
  format: string;
  vtt_url: string;
}

export interface Video {
  id: number;
  file_path: string;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  codec: string | null;
  thumbnail_path: string | null;
  source: string;
  description?: string | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
  fps?: number | null;
  bitrate_kbps?: number | null;
}

export type PendingSpec = PendingUploadSpec & { key: string };

export const PROGRAMS_LIST_ID = "library-programs";
export const SUBTITLE_ACCEPT = ".srt,.vtt,text/vtt,application/x-subrip";
