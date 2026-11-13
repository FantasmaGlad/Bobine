export interface AudioTrack {
  id: number;
  number: number | null;
  title: string;
  duration_seconds: number | null;
  position: number;
  background_id?: number | null;
  background_title?: string | null;
  background_is_image?: boolean;
}

export interface AudioCourseSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  background_id: number | null;
  background_thumbnail_path: string | null;
  track_count: number;
  total_duration_seconds: number;
}

export interface AudioCourseDetail extends AudioCourseSummary {
  tracks: AudioTrack[];
}

export interface BackgroundOption {
  id: number;
  title: string;
  thumbnail_path?: string | null;
  is_image?: boolean;
}

export const PROGRAMS_LIST_ID = "audio-programs";
