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
};

export function formatEta(seconds: number | null | undefined): string | null {
  if (typeof seconds !== "number" || isNaN(seconds) || seconds < 0) return null;
  if (seconds < 60) return `~${seconds}s restantes`;
  const mins = Math.floor(seconds / 60);
  const remSecs = seconds % 60;
  return remSecs > 0 ? `~${mins} min ${remSecs}s restantes` : `~${mins} min restantes`;
}

export function formatQueueSuffix(queuePosition: number | null | undefined, queueEtaSeconds: number | null | undefined): string {
  if (typeof queuePosition !== "number" || queuePosition <= 0) return "";
  const eta = formatEta(queueEtaSeconds);
  const etaSuffix = eta ? `, ${eta.replace("restantes", "au total")}` : "";
  return ` (${queuePosition} devant${etaSuffix})`;
}
