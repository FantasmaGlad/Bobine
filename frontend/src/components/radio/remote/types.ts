export type SendRadioCommand = (command: string, params?: Record<string, unknown>) => void;

export interface RadioPlaylistSummary {
  id: number;
  name: string;
  is_default: boolean;
  item_count: number;
  total_duration_seconds: number;
  cover_track_id?: number | null;
}

export interface RadioTrackSearchResult {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  genre?: string | null;
  duration_seconds: number | null;
  has_cover?: boolean;
}
