import { getApiUrl } from "@/lib/apiUrl";

export function formatDuration(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function getThumbnailSrc(thumb?: string | null): string | null {
  if (!thumb) return null;
  const filename = thumb.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

export type OsdContent = { icon: string; label: string } | null;

export interface NextCourse {
  run_at: string;
  title: string | null;
}
