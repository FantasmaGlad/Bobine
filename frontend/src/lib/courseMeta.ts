export interface CourseLike {
  id: number;
  title: string;
  program?: string | null;
  release?: string | null;
  duration_seconds?: number | null;
  thumbnail_url?: string | null;
  thumbnail_path?: string | null;
  description?: string | null;
  width?: number | null;
  height?: number | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
}

/** Adresse de la miniature, que le serveur donne en chemin complet ou en nom de fichier. */
export function courseThumbSrc(getApiUrl: (path: string) => string, course: Pick<CourseLike, "thumbnail_url" | "thumbnail_path">): string | null {
  const raw = course.thumbnail_url || course.thumbnail_path;
  if (!raw) return null;
  const filename = raw.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

/** 42:10 ou 1:05:30 ; « --:-- » sans durée connue. */
export function formatClock(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "--:--";
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

/** Secondes depuis « 90 », « 1:30 » ou « 1:02:03 » ; null si illisible. */
export function parseClock(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (/^\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  const match = /^(?:(\d+):)?(\d{1,3}):(\d{2})(?:[.,](\d{1,3}))?$/.exec(trimmed);
  if (!match) return null;
  const [, h, m, s, ms] = match;
  return Number(h ?? 0) * 3600 + Number(m) * 60 + Number(s) + (ms ? Number(`0.${ms}`) : 0);
}
