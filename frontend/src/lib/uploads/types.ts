import type { UploadNotice, UploadPhase } from "@/lib/uploadFlow";

export type UploadKind =
  | "video" | "background" | "video_zip" | "background_zip" | "audio_files" | "audio_zip"
  | "radio_files" | "radio_zip" | "radio_announcement_files" | "visual" | "visual_zip";

export interface PendingUploadSpec {
  kind: UploadKind;
  file?: File;
  files?: File[];
  title: string;
  program?: string | null;
  release?: string | null;
  description?: string | null;
  subtitles?: File[];
}

export type UploadTaskStatus = "pending" | "uploading" | "processing" | "done" | "error";

export interface UploadTask extends PendingUploadSpec {
  id: string;
  status: UploadTaskStatus;
  progress: number;
  uploadEtaSeconds?: number | null;
  jobId?: string;
  stage?: string;
  stageLabel?: string;
  progressPercent?: number | null;
  etaSeconds?: number | null;
  speed?: string | null;
  queuePosition?: number | null;
  estimatedSeconds?: number | null;
  queueEtaSeconds?: number | null;
  resultId?: number | null;
  error?: string;
  errorNotice?: UploadNotice;
  phase?: UploadPhase;
  notice?: UploadNotice | null;
  xhr?: XMLHttpRequest;
  abort?: () => void;
}

export interface ImportJobStatus {
  id: string;
  stage: string;
  stage_label: string;
  queue_position: number | null;
  error: string | null;
  error_code?: string | null;
  error_params?: Record<string, unknown> | null;
  result_id: number | null;
  progress_percent: number | null;
  eta_seconds: number | null;
  speed: string | null;
  estimated_seconds: number | null;
  queue_eta_seconds: number | null;
}

export interface TaskControls {
  update: (patch: Partial<UploadTask>) => void;
  remove: () => void;
  done: () => void;
}
