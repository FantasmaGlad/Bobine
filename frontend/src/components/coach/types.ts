export interface AudioCourseSummary {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  track_count: number;
  total_duration_seconds: number;
}

export interface AudioPlaylistSummary {
  id: number;
  name: string;
  item_count: number;
  total_duration_seconds: number;
}

export interface BackgroundSummary {
  id: number;
  title: string;
  is_image: boolean;
  thumbnail_path: string | null;
  duration_seconds: number | null;
}
