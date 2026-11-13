"use client";
import { errorMessage } from "@/lib/apiError";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { translate } from "@/lib/i18n";
import {
  ChunkedUnsupportedError,
  UploadAbortedError,
  UploadNoticeError,
  cancelChunkedUpload,
  uploadFileInChunks,
} from "@/lib/chunkedUpload";
import {
  isJobLost,
  isServerSilent,
  jobErrorNotice,
  nextMissCount,
  nextPollFailures,
  type UploadNotice,
  type UploadPhase,
} from "@/lib/uploadFlow";
import { getApiUrl } from "@/lib/apiUrl";
import UploadFloatingPanel from "@/components/uploads/UploadFloatingPanel";

const JOB_POLL_INTERVAL_MS = 1500;
const PROGRESS_MIN_INTERVAL_MS = 250;

function maxConcurrentUploads(): number {
  const cores = typeof navigator !== "undefined" ? navigator.hardwareConcurrency || 4 : 4;
  if (cores <= 3) return 1;
  if (cores <= 7) return 2;
  return 3;
}

const CHUNKED_KINDS: ReadonlySet<UploadKind> = new Set<UploadKind>(["video", "background", "video_zip", "background_zip", "audio_zip", "radio_zip"]);

export type UploadKind =
  | "video" | "background" | "video_zip" | "background_zip" | "audio_files" | "audio_zip"
  | "radio_files" | "radio_zip" | "radio_announcement_files";

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

interface UploadManagerContextValue {
  uploads: UploadTask[];
  addUploads: (specs: PendingUploadSpec[]) => void;
  cancelUpload: (id: string) => void;
  clearCompleted: () => void;
}

const UploadManagerContext = createContext<UploadManagerContextValue | null>(null);

function uuid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

const UPLOAD_ENDPOINTS: Record<UploadKind, string> = {
  video: "/videos/upload",
  background: "/backgrounds/upload",
  video_zip: "/videos/upload-zip",
  background_zip: "/backgrounds/upload-zip",
  audio_files: "/audio/upload",
  audio_zip: "/audio/upload-zip",
  radio_files: "/radio/tracks/upload",
  radio_zip: "/radio/tracks/upload-zip",
  radio_announcement_files: "/radio/announcements/upload-batch",
};

export function UploadManagerProvider({ children }: { children: React.ReactNode }) {
  const [uploads, setUploads] = useState<UploadTask[]>([]);
  const uploadsRef = useRef<UploadTask[]>([]);

  const updateTask = useCallback((id: string, patch: Partial<UploadTask>) => {
    setUploads((prev) => {
      const next = prev.map((t) => (t.id === id ? { ...t, ...patch } : t));
      uploadsRef.current = next;
      return next;
    });
  }, []);

  const buildFormData = (task: UploadTask, uploadId?: string): FormData => {
    const formData = new FormData();
    if (uploadId) {
      formData.append("upload_id", uploadId);
    } else if (task.kind === "audio_files" || task.kind === "radio_files" || task.kind === "radio_announcement_files") {
      (task.files ?? []).forEach((f) => formData.append("files", f));
    } else if (task.file) {
      formData.append("file", task.file);
    }
    formData.append("title", task.title);
    if (task.kind === "video" || task.kind === "audio_files" || task.kind === "audio_zip") {
      if (task.program) formData.append("program", task.program);
      if (task.release) formData.append("release", task.release);
      if (task.description) formData.append("description", task.description);
      if (task.subtitles && task.subtitles.length > 0) {
        task.subtitles.forEach((sub) => formData.append("subtitles", sub));
      }
    }
    return formData;
  };

  const makeProgressReporter = useCallback(
    (taskId: string) => {
      const startTime = Date.now();
      let lastUpdateAt = 0;
      return (loaded: number, total: number) => {
        if (total <= 0) return;
        const now = Date.now();
        if (loaded < total && lastUpdateAt !== 0 && now - lastUpdateAt < PROGRESS_MIN_INTERVAL_MS) return;
        lastUpdateAt = now;
        const elapsedSec = (now - startTime) / 1000;
        let uploadEtaSeconds: number | null = null;
        if (elapsedSec > 0.5 && loaded > 0) {
          uploadEtaSeconds = Math.max(0, Math.round((total - loaded) / (loaded / elapsedSec)));
        }
        updateTask(taskId, { progress: Math.round((loaded / total) * 100), uploadEtaSeconds });
      };
    },
    [updateTask],
  );

  const runChunkedUpload = useCallback(
    (task: UploadTask, onDone: () => void, fallback: () => void) => {
      const controller = new AbortController();
      let sessionId: string | undefined;
      updateTask(task.id, { status: "uploading", phase: "connecting", notice: null, abort: () => controller.abort() });
      const report = makeProgressReporter(task.id);

      (async () => {
        const uploadId = await uploadFileInChunks(task.file!, {
          apiUrl: getApiUrl,
          signal: controller.signal,
          onSession: (id) => { sessionId = id; },
          onProgress: report,
          onPhase: (phase) => updateTask(task.id, { phase }),
          onNotice: (notice) => updateTask(task.id, { notice }),
        });
        sessionId = uploadId;
        const res = await fetch(getApiUrl(UPLOAD_ENDPOINTS[task.kind]), {
          method: "POST",
          body: buildFormData(task, uploadId),
          signal: controller.signal,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(errorMessage(body, translate("uploadManager.importError")));
        }
        const body = await res.json().catch(() => ({}));
        updateTask(task.id, {
          status: body.job_id ? "processing" : "done",
          progress: 100,
          jobId: body.job_id,
          stage: "queued",
          stageLabel: translate("common.pending"),
          phase: "processing",
          notice: null,
          abort: undefined,
        });
        onDone();
      })().catch((err: unknown) => {
        const aborted = err instanceof UploadAbortedError || (err as DOMException)?.name === "AbortError";
        if (err instanceof ChunkedUnsupportedError) {
          fallback();
          return;
        }
        if (aborted) {
          if (sessionId) void cancelChunkedUpload(sessionId, getApiUrl);
          setUploads((prev) => {
            const next = prev.filter((t) => t.id !== task.id);
            uploadsRef.current = next;
            return next;
          });
        } else {
          updateTask(task.id, {
            status: "error",
            error: (err as Error).message || translate("uploadManager.uploadError"),
            errorNotice: err instanceof UploadNoticeError ? { key: err.key, params: err.params } : undefined,
            notice: null,
            abort: undefined,
          });
        }
        onDone();
      });
    },
    [updateTask, makeProgressReporter],
  );

  const runMultipartUpload = useCallback(
    (task: UploadTask, onDone: () => void) => {
      const xhr = new XMLHttpRequest();
      updateTask(task.id, { status: "uploading", phase: "sending", notice: null, xhr });

      const report = makeProgressReporter(task.id);
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) report(e.loaded, e.total);
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const body = JSON.parse(xhr.responseText);
            updateTask(task.id, {
              status: "processing",
              progress: 100,
              jobId: body.job_id,
              stage: "queued",
              stageLabel: translate("common.pending"),
              phase: "processing",
            });
          } catch {
            updateTask(task.id, { status: "done", progress: 100 });
          }
        } else {
          let errMsg = translate("uploadManager.uploadError");
          try {
            const body = JSON.parse(xhr.responseText);
            errMsg = errorMessage(body, errMsg);
          } catch {
          }
          updateTask(task.id, { status: "error", error: errMsg });
        }
        onDone();
      });

      xhr.addEventListener("error", () => {
        updateTask(task.id, { status: "error", error: translate("common.networkError") });
        onDone();
      });

      xhr.addEventListener("abort", () => {
        setUploads((prev) => {
          const next = prev.filter((t) => t.id !== task.id);
          uploadsRef.current = next;
          return next;
        });
        onDone();
      });

      xhr.open("POST", getApiUrl(UPLOAD_ENDPOINTS[task.kind]));
      xhr.send(buildFormData(task));
    },
    [updateTask, makeProgressReporter],
  );

  const runUpload = useCallback(
    (task: UploadTask, onDone: () => void) => {
      const multipart = () => runMultipartUpload(task, onDone);
      if (CHUNKED_KINDS.has(task.kind) && task.file) {
        runChunkedUpload(task, onDone, multipart);
        return;
      }
      multipart();
    },
    [runChunkedUpload, runMultipartUpload],
  );

  const fillSlotsRef = useRef<() => void>(() => {});
  const fillSlots = useCallback(() => {
    const activeCount = uploadsRef.current.filter((t) => t.status === "uploading").length;
    const slotsFree = maxConcurrentUploads() - activeCount;
    if (slotsFree <= 0) return;
    const toStart = uploadsRef.current.filter((t) => t.status === "pending").slice(0, slotsFree);
    toStart.forEach((task) => runUpload(task, () => fillSlotsRef.current()));
  }, [runUpload]);
  useEffect(() => {
    fillSlotsRef.current = fillSlots;
  }, [fillSlots]);

  const addUploads = useCallback(
    (specs: PendingUploadSpec[]) => {
      const newTasks: UploadTask[] = specs.map((spec) => ({
        ...spec,
        id: uuid(),
        status: "pending",
        progress: 0,
      }));

      setUploads((prev) => {
        const next = [...prev, ...newTasks];
        uploadsRef.current = next;
        return next;
      });

      setTimeout(fillSlots, 0);
    },
    [fillSlots],
  );

  const cancelUpload = useCallback((id: string) => {
    const task = uploadsRef.current.find((t) => t.id === id);
    if (!task) return;

    if (task.jobId) {
      fetch(getApiUrl(`/import-jobs/${task.jobId}`), { method: "DELETE" }).catch((e) => {
        console.error("Erreur lors de l'annulation de la tâche sur le serveur:", e);
      });
    }

    if (task.status === "uploading" && (task.xhr || task.abort)) {
      if (task.xhr) task.xhr.abort();
      else task.abort?.();
    } else {
      setUploads((prev) => {
        const next = prev.filter((t) => t.id !== id);
        uploadsRef.current = next;
        return next;
      });
    }
  }, []);

  const clearCompleted = useCallback(() => {
    setUploads((prev) => {
      const next = prev.filter((t) => t.status === "uploading" || t.status === "pending" || t.status === "processing");
      uploadsRef.current = next;
      return next;
    });
  }, []);

  const missCountsRef = useRef<Map<string, number>>(new Map());
  const pollFailuresRef = useRef(0);
  useEffect(() => {
    const interval = setInterval(() => {
      const processing = uploadsRef.current.filter((t) => t.status === "processing" && t.jobId);
      if (processing.length === 0) {
        missCountsRef.current.clear();
        pollFailuresRef.current = 0;
        return;
      }
      fetch(getApiUrl("/import-jobs"), { cache: "no-store" })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((jobs: Array<{
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
        }>) => {
          pollFailuresRef.current = nextPollFailures(pollFailuresRef.current, true);
          const byId = new Map(jobs.map((j) => [j.id, j]));
          const misses = missCountsRef.current;
          const stillProcessing = new Set(processing.map((t) => t.id));
          for (const id of [...misses.keys()]) if (!stillProcessing.has(id)) misses.delete(id);
          processing.forEach((task) => {
            const job = task.jobId ? byId.get(task.jobId) : undefined;
            const missCount = nextMissCount(misses.get(task.id), job !== undefined);
            if (job) misses.delete(task.id);
            else misses.set(task.id, missCount);
            if (!job) {
              if (isJobLost(missCount)) {
                misses.delete(task.id);
                updateTask(task.id, {
                  status: "error",
                  error: translate("uploadManager.taskLost"),
                  errorNotice: { key: "uploads.errors.jobLost" },
                  notice: null,
                  queuePosition: null,
                });
              } else if (task.notice) {
                updateTask(task.id, { notice: null });
              }
              return;
            }
            if (task.notice) updateTask(task.id, { notice: null });
            if (job.stage === "done") {
              updateTask(task.id, {
                status: "done",
                stage: job.stage,
                stageLabel: job.stage_label,
                resultId: job.result_id,
                queuePosition: null,
                progressPercent: 100,
                etaSeconds: 0,
              });
            } else if (job.stage === "error") {
              updateTask(task.id, {
                status: "error",
                stage: job.stage,
                stageLabel: job.stage_label,
                error: job.error || translate("uploadManager.importFailed"),
                errorNotice: jobErrorNotice(job.error_code, job.error_params),
                queuePosition: null,
              });
            } else if (job.stage === "cancelled") {
              setUploads((prev) => {
                const next = prev.filter((t) => t.id !== task.id);
                uploadsRef.current = next;
                return next;
              });
            } else {
              updateTask(task.id, {
                stage: job.stage,
                stageLabel: job.stage_label,
                queuePosition: job.queue_position ?? null,
                progressPercent: job.progress_percent,
                etaSeconds: job.eta_seconds,
                speed: job.speed,
                estimatedSeconds: job.estimated_seconds,
                queueEtaSeconds: job.queue_eta_seconds,
              });
            }
          });
        })
        .catch(() => {
          pollFailuresRef.current = nextPollFailures(pollFailuresRef.current, false);
          if (isServerSilent(pollFailuresRef.current)) {
            processing.forEach((task) => {
              if (task.notice?.key !== "uploads.serverUnreachable") {
                updateTask(task.id, { notice: { key: "uploads.serverUnreachable" } });
              }
            });
          }
        });
    }, JOB_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [updateTask]);

  return (
    <UploadManagerContext.Provider value={{ uploads, addUploads, cancelUpload, clearCompleted }}>
      {children}
      <UploadFloatingPanel />
    </UploadManagerContext.Provider>
  );
}

export function useUploadManager(): UploadManagerContextValue {
  const ctx = useContext(UploadManagerContext);
  if (!ctx) throw new Error("useUploadManager must be used inside <UploadManagerProvider>");
  return ctx;
}
