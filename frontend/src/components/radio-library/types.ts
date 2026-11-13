export interface RadioTrack {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  album_artist: string | null;
  track_number: number | null;
  disc_number: number | null;
  year: number | null;
  genre: string | null;
  duration_seconds: number | null;
  has_cover: boolean;
  tags: string[];
}

export interface PlaylistSummary {
  id: number;
  name: string;
  is_default: boolean;
  item_count: number;
  total_duration_seconds: number;
  cover_track_id: number | null;
}

export interface PlaylistItem {
  id: number;
  position: number;
  track: { id: number; title: string; artist: string | null; album: string | null; duration_seconds: number | null; has_cover: boolean };
}

export interface PlaylistDetail {
  id: number;
  name: string;
  is_default: boolean;
  items: PlaylistItem[];
  total_duration_seconds: number;
}

export interface ArtistEntry { name: string; track_count: number; album_count: number }
export interface AlbumEntry { album: string; album_artist: string | null; track_count: number; year: number | null; cover_track_id: number | null }
export interface TagEntry { id: number; name: string; track_count: number }

export type Filter = { type: "artist" | "album" | "genre" | "tag" | "playlist"; value: string } | null;
export type Section = "tracks" | "playlists" | "artists" | "tags" | "import";
export type SortKey = "recent" | "title" | "artist" | "duration";
export type ViewMode = "grid" | "list";
export type RadioOutput = "radio_cable" | "radio_network";
export type OutputDefaults = Record<string, { override_playlist_id: number | null; effective_playlist_id: number | null }>;
