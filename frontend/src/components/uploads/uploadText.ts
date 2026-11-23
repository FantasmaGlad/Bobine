import type { UploadKind } from "@/lib/uploads/types";

export const STAGE_ICONS: Record<string, string> = {
  queued: "hourglass_empty",
  probing: "search",
  normalizing: "autorenew",
  copying: "drive_file_move",
  thumbnail: "image",
  extracting: "folder_zip",
  saving: "save",
};

export const KIND_LABEL_KEYS: Record<UploadKind, string> = {
  video: "uploadManager.kindVideo",
  background: "uploadManager.kindBackground",
  video_zip: "uploadManager.kindVideo",
  background_zip: "uploadManager.kindBackground",
  audio_files: "uploadManager.kindAudio",
  audio_zip: "uploadManager.kindAudio",
  radio_files: "uploadManager.kindRadio",
  radio_zip: "uploadManager.kindRadio",
  radio_announcement_files: "uploadManager.kindAnnouncements",
  visual: "uploadManager.kindVisual",
  visual_zip: "uploadManager.kindVisual",
};

type Translate = (key: string, vars?: Record<string, string | number>) => string;

const ETA_KEYS = {
  remaining: "uploadManager.etaRemaining",
  estimate: "uploadManager.etaEstimate",
  total: "uploadManager.etaTotal",
} as const;

function formatDuration(seconds: number): string {
  if (seconds < 60) return `~${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const remSecs = seconds % 60;
  return remSecs > 0 ? `~${mins} min ${remSecs}s` : `~${mins} min`;
}

export function formatEta(
  t: Translate,
  seconds: number | null | undefined,
  mode: keyof typeof ETA_KEYS = "remaining",
): string | null {
  if (typeof seconds !== "number" || isNaN(seconds) || seconds < 0) return null;
  return t(ETA_KEYS[mode], { duration: formatDuration(seconds) });
}

export function formatQueueSuffix(
  t: Translate,
  queuePosition: number | null | undefined,
  queueEtaSeconds: number | null | undefined,
): string {
  if (typeof queuePosition !== "number" || queuePosition <= 0) return "";
  const eta = formatEta(t, queueEtaSeconds, "total");
  const ahead = t("uploadManager.queueAhead", { count: queuePosition });
  return eta ? ` (${ahead}, ${eta})` : ` (${ahead})`;
}
