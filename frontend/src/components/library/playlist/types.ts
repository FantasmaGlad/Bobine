export interface Video {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
}

export interface PlaylistItemInput {
  video_id: number;
  position: number;
}

export interface PlaylistItemResponse {
  id: number;
  position: number;
  video: Video;
}

export interface PlaylistDetail {
  id: number;
  name: string;
  created_at: string;
  items: PlaylistItemResponse[];
  total_duration_seconds: number;
}

export type { PlaylistSummary } from "@/components/PlaylistList";

export type Sequencer = ReturnType<typeof import("@/lib/usePlaylistSequencer").usePlaylistSequencer<Video>>;

export function formatItemDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "--:--";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
