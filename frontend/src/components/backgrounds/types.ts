export interface BackgroundItem {
  id: number;
  file_path: string;
  title: string;
  duration_seconds: number | null;
  thumbnail_path: string | null;
  is_image: boolean;
}
