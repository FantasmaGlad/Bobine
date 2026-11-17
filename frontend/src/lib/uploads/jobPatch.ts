import { translate } from "@/lib/i18n";
import { jobErrorNotice } from "@/lib/uploadFlow";
import type { ImportJobStatus, UploadTask } from "./types";

export function jobPatch(job: ImportJobStatus): Partial<UploadTask> | "remove" {
  if (job.stage === "done") {
    return {
      status: "done",
      stage: job.stage,
      stageLabel: job.stage_label,
      resultId: job.result_id,
      queuePosition: null,
      progressPercent: 100,
      etaSeconds: 0,
    };
  }
  if (job.stage === "error") {
    return {
      status: "error",
      stage: job.stage,
      stageLabel: job.stage_label,
      error: job.error || translate("uploadManager.importFailed"),
      errorNotice: jobErrorNotice(job.error_code, job.error_params),
      queuePosition: null,
    };
  }
  if (job.stage === "cancelled") return "remove";
  return {
    stage: job.stage,
    stageLabel: job.stage_label,
    queuePosition: job.queue_position ?? null,
    progressPercent: job.progress_percent,
    etaSeconds: job.eta_seconds,
    speed: job.speed,
    estimatedSeconds: job.estimated_seconds,
    queueEtaSeconds: job.queue_eta_seconds,
  };
}
