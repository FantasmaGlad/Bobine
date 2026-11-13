export interface AudioTrackSummary {
  id: number;
  number: number | null;
  title: string;
  duration_seconds: number | null;
  course_id: number;
  course_title: string;
  course_program: string | null;
}

export interface AudioCourseSummary {
  id: number;
  title: string;
  program: string | null;
  background_thumbnail_path: string | null;
  track_count: number;
}

export interface AudioPlaylistItemInput {
  audio_track_id: number;
  position: number;
  background_id: number | null;
}

export interface AudioPlaylistItemBackground {
  id: number;
  title: string;
  is_image: boolean;
}

export interface AudioPlaylistItemResponse {
  id: number;
  position: number;
  track: AudioTrackSummary;
  background: AudioPlaylistItemBackground | null;
}

export interface AudioPlaylistDetail {
  id: number;
  name: string;
  created_at: string;
  items: AudioPlaylistItemResponse[];
  total_duration_seconds: number;
}

export type { PlaylistSummary as AudioPlaylistSummary } from "@/components/PlaylistList";

export interface BackgroundSummary {
  id: number;
  title: string;
  is_image: boolean;
}

export interface PlaylistDraftItem {
  track: AudioTrackSummary;
  backgroundId: number | null;
}

export type Sequencer = ReturnType<typeof import("@/lib/usePlaylistSequencer").usePlaylistSequencer<PlaylistDraftItem>>;
