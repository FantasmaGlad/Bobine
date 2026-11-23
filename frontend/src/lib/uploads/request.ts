import type { UploadKind, UploadTask } from "./types";

export const UPLOAD_ENDPOINTS: Record<UploadKind, string> = {
  video: "/videos/upload",
  background: "/backgrounds/upload",
  video_zip: "/videos/upload-zip",
  background_zip: "/backgrounds/upload-zip",
  audio_files: "/audio/upload",
  audio_zip: "/audio/upload-zip",
  radio_files: "/radio/tracks/upload",
  radio_zip: "/radio/tracks/upload-zip",
  radio_announcement_files: "/radio/announcements/upload-batch",
  visual: "/visuals/upload",
  visual_zip: "/visuals/upload-zip",
};

export const CHUNKED_KINDS: ReadonlySet<UploadKind> = new Set<UploadKind>(["video", "background", "video_zip", "background_zip", "audio_zip", "radio_zip", "visual", "visual_zip"]);

const MULTI_FILE_KINDS: ReadonlySet<UploadKind> = new Set<UploadKind>(["audio_files", "radio_files", "radio_announcement_files"]);
const DESCRIBED_KINDS: ReadonlySet<UploadKind> = new Set<UploadKind>(["video", "audio_files", "audio_zip"]);

export function maxConcurrentUploads(): number {
  const cores = typeof navigator !== "undefined" ? navigator.hardwareConcurrency || 4 : 4;
  if (cores <= 3) return 1;
  if (cores <= 7) return 2;
  return 3;
}

export function buildFormData(task: UploadTask, uploadId?: string): FormData {
  const formData = new FormData();
  if (uploadId) {
    formData.append("upload_id", uploadId);
  } else if (MULTI_FILE_KINDS.has(task.kind)) {
    (task.files ?? []).forEach((f) => formData.append("files", f));
  } else if (task.file) {
    formData.append("file", task.file);
  }
  formData.append("title", task.title);
  if (DESCRIBED_KINDS.has(task.kind)) {
    if (task.program) formData.append("program", task.program);
    if (task.release) formData.append("release", task.release);
    if (task.description) formData.append("description", task.description);
    if (task.subtitles && task.subtitles.length > 0) {
      task.subtitles.forEach((sub) => formData.append("subtitles", sub));
    }
  }
  return formData;
}
