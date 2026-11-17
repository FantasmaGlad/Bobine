import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import {
  ChunkedUnsupportedError,
  UploadAbortedError,
  UploadNoticeError,
  cancelChunkedUpload,
  uploadFileInChunks,
} from "@/lib/chunkedUpload";
import { translate } from "@/lib/i18n";
import { progressReporter } from "./progress";
import { UPLOAD_ENDPOINTS, buildFormData } from "./request";
import type { TaskControls, UploadTask } from "./types";

const QUEUED = { stage: "queued", phase: "processing" } as const;

async function sendChunked(task: UploadTask, controls: TaskControls, signal: AbortSignal, onSession: (id: string) => void) {
  const uploadId = await uploadFileInChunks(task.file!, {
    apiUrl: getApiUrl,
    signal,
    onSession,
    onProgress: progressReporter(controls.update),
    onPhase: (phase) => controls.update({ phase }),
    onNotice: (notice) => controls.update({ notice }),
  });
  onSession(uploadId);
  const res = await fetch(getApiUrl(UPLOAD_ENDPOINTS[task.kind]), {
    method: "POST",
    body: buildFormData(task, uploadId),
    signal,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(errorMessage(body, translate("uploadManager.importError")));
  }
  const body = await res.json().catch(() => ({}));
  controls.update({
    status: body.job_id ? "processing" : "done",
    progress: 100,
    jobId: body.job_id,
    ...QUEUED,
    stageLabel: translate("common.pending"),
    notice: null,
    abort: undefined,
  });
}

export function runChunkedUpload(task: UploadTask, controls: TaskControls, fallback: () => void) {
  const controller = new AbortController();
  let sessionId: string | undefined;
  controls.update({ status: "uploading", phase: "connecting", notice: null, abort: () => controller.abort() });
  sendChunked(task, controls, controller.signal, (id) => { sessionId = id; })
    .then(controls.done)
    .catch((err: unknown) => {
      if (err instanceof ChunkedUnsupportedError) {
        fallback();
        return;
      }
      const aborted = err instanceof UploadAbortedError || (err as DOMException)?.name === "AbortError";
      if (aborted) {
        if (sessionId) void cancelChunkedUpload(sessionId, getApiUrl);
        controls.remove();
      } else {
        controls.update({
          status: "error",
          error: (err as Error).message || translate("uploadManager.uploadError"),
          errorNotice: err instanceof UploadNoticeError ? { key: err.key, params: err.params } : undefined,
          notice: null,
          abort: undefined,
        });
      }
      controls.done();
    });
}

function multipartError(xhr: XMLHttpRequest): string {
  const fallback = translate("uploadManager.uploadError");
  try {
    return errorMessage(JSON.parse(xhr.responseText), fallback);
  } catch {
    return fallback;
  }
}

function onMultipartLoad(xhr: XMLHttpRequest, controls: TaskControls) {
  if (xhr.status < 200 || xhr.status >= 300) {
    controls.update({ status: "error", error: multipartError(xhr) });
    return;
  }
  try {
    const body = JSON.parse(xhr.responseText);
    controls.update({ status: "processing", progress: 100, jobId: body.job_id, ...QUEUED, stageLabel: translate("common.pending") });
  } catch {
    controls.update({ status: "done", progress: 100 });
  }
}

export function runMultipartUpload(task: UploadTask, controls: TaskControls) {
  const xhr = new XMLHttpRequest();
  controls.update({ status: "uploading", phase: "sending", notice: null, xhr });
  const report = progressReporter(controls.update);
  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) report(e.loaded, e.total);
  });
  xhr.addEventListener("load", () => {
    onMultipartLoad(xhr, controls);
    controls.done();
  });
  xhr.addEventListener("error", () => {
    controls.update({ status: "error", error: translate("common.networkError") });
    controls.done();
  });
  xhr.addEventListener("abort", () => {
    controls.remove();
    controls.done();
  });
  xhr.open("POST", getApiUrl(UPLOAD_ENDPOINTS[task.kind]));
  xhr.send(buildFormData(task));
}
