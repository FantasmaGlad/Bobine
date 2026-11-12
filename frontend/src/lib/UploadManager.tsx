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
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { translate } from "@/lib/i18n";
import {
  ChunkedUnsupportedError,
  UploadAbortedError,
  UploadNoticeError,
  cancelChunkedUpload,
  uploadFileInChunks,
} from "@/lib/chunkedUpload";
import {
  formatNotice,
  isJobLost,
  isServerSilent,
  jobErrorNotice,
  nextMissCount,
  nextPollFailures,
  phaseLabelKey,
  type UploadNotice,
  type UploadPhase,
} from "@/lib/uploadFlow";
import { getApiUrl } from "@/lib/apiUrl";

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

const STAGE_ICONS: Record<string, string> = {
  queued: "hourglass_empty",
  probing: "search",
  normalizing: "autorenew",
  copying: "drive_file_move",
  thumbnail: "image",
  extracting: "folder_zip",
  saving: "save",
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
          stageLabel: "En attente",
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
              stageLabel: "En attente",
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

  const fillSlots = useCallback(() => {
    const activeCount = uploadsRef.current.filter((t) => t.status === "uploading").length;
    const slotsFree = maxConcurrentUploads() - activeCount;
    if (slotsFree <= 0) return;
    const toStart = uploadsRef.current.filter((t) => t.status === "pending").slice(0, slotsFree);
    toStart.forEach((task) => runUpload(task, fillSlots));
  }, [runUpload]);

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

const KIND_LABEL_KEYS: Record<UploadKind, string> = {
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

function formatEta(seconds: number | null | undefined): string | null {
  if (typeof seconds !== "number" || isNaN(seconds) || seconds < 0) return null;
  if (seconds < 60) return `~${seconds}s restantes`;
  const mins = Math.floor(seconds / 60);
  const remSecs = seconds % 60;
  return remSecs > 0 ? `~${mins} min ${remSecs}s restantes` : `~${mins} min restantes`;
}

function formatQueueSuffix(queuePosition: number | null | undefined, queueEtaSeconds: number | null | undefined): string {
  if (typeof queuePosition !== "number" || queuePosition <= 0) return "";
  const eta = formatEta(queueEtaSeconds);
  const etaSuffix = eta ? `, ${eta.replace("restantes", "au total")}` : "";
  return ` (${queuePosition} devant${etaSuffix})`;
}

function UploadFloatingPanel() {
  const { uploads, cancelUpload, clearCompleted } = useContext(UploadManagerContext)!;
  const { t } = useAppSettings();
  const [minimized, setMinimized] = useState(false);

  const visible = uploads.length > 0;
  if (!visible) return null;

  const active = uploads.filter((u) => u.status === "uploading" || u.status === "pending" || u.status === "processing");
  const completed = uploads.filter((u) => u.status === "done" || u.status === "error");

  return (
    <div
      style={{
        position: "fixed",
        bottom: "24px",
        right: "24px",
        zIndex: 9999,
        width: minimized ? "auto" : "420px",
        background: "var(--bg-surface-elevated)",
        border: "1px solid var(--border-color)",
        borderRadius: "12px",
        boxShadow: "0 8px 32px color-mix(in srgb, var(--ink) 40%, transparent)",
        overflow: "hidden",
        fontFamily: "var(--font-body)",
        fontSize: "0.85rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          background: "var(--bg-surface-hover)",
          borderBottom: minimized ? "none" : "1px solid var(--border-color)",
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setMinimized((m) => !m)}
      >
        <span style={{ fontWeight: 700, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
          <Icon name="upload" size={16} />
          {active.length > 0
            ? t(active.length > 1 ? "uploadManager.activeMany" : "uploadManager.activeOne", { count: active.length })
            : t(completed.length > 1 ? "uploadManager.doneMany" : "uploadManager.doneOne", { count: completed.length })}
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", display: "flex", alignItems: "center" }}>
          <Icon name={minimized ? "expand_less" : "expand_more"} size={16} />
        </span>
      </div>

      {!minimized && (
        <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px", maxHeight: "320px", overflowY: "auto" }}>
          {uploads.map((task) => (
            <div key={task.id} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span
                  style={{
                    color: task.status === "error" ? "var(--accent-error-text)" : task.status === "done" ? "var(--accent-success-text)" : "var(--text-main)",
                    fontWeight: 600,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: "230px",
                    flexShrink: 1,
                    minWidth: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                  title={task.title}
                >
                  {task.status === "done" && <Icon name="check" size={14} color="var(--accent-success-text)" />}
                  {task.status === "error" && <Icon name="close" size={14} color="var(--accent-error-text)" />}
                  {task.status === "pending" && <Icon name="hourglass_empty" size={14} />}
                  {task.status === "processing" && (
                    <Icon name={STAGE_ICONS[task.stage ?? ""] ?? "autorenew"} size={14} className="olc-spin" />
                  )}
                  {task.title}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, whiteSpace: "nowrap" }}>
                  {task.status === "uploading" && (
                    <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      {task.progress}%{task.uploadEtaSeconds ? ` (${formatEta(task.uploadEtaSeconds)})` : ""}
                    </span>
                  )}
                  {(task.status === "uploading" || task.status === "pending" || task.status === "processing") && (
                    <button
                      onClick={() => cancelUpload(task.id)}
                      title={t("uploadManager.cancelImport")}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        padding: "2px 4px",
                        fontSize: "0.9rem",
                        lineHeight: 1,
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      <Icon name="close" size={14} />
                    </button>
                  )}
                </div>
              </div>
              <span style={{ color: "var(--text-dim)", fontSize: "0.72rem" }}>
                {t(KIND_LABEL_KEYS[task.kind])}
                {task.status === "uploading" && (
                  <>{" — "}{t(phaseLabelKey(task.phase ?? "sending"))}</>
                )}
                {task.status === "processing" && (
                  <>
                    {" — "}
                    {t(phaseLabelKey("processing"))}{" : "}
                    {task.stage === "normalizing" && typeof task.progressPercent === "number" ? (
                      <>
                        {t("uploadManager.reencoding", { percent: task.progressPercent })}
                        {typeof task.etaSeconds === "number" ? (
                          ` — ${formatEta(task.etaSeconds)}`
                        ) : typeof task.estimatedSeconds === "number" ? (
                          ` — ${formatEta(task.estimatedSeconds)} (estimation)`
                        ) : null}
                        {task.speed && ` (${task.speed})`}
                      </>
                    ) : (
                      <>
                        {task.stageLabel ?? "Traitement…"}
                        {task.stage === "normalizing" && typeof task.estimatedSeconds === "number" &&
                          ` — ${formatEta(task.estimatedSeconds)} (estimation)`}
                      </>
                    )}
                    {formatQueueSuffix(task.queuePosition, task.queueEtaSeconds)}
                  </>
                )}
              </span>
              {task.status === "uploading" && (
                <div style={{ height: "3px", background: "var(--border-color)", borderRadius: "2px" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${task.progress}%`,
                      background: "var(--accent-primary)",
                      borderRadius: "2px",
                      transition: "width 0.2s",
                    }}
                  />
                </div>
              )}
              {task.status === "processing" && (
                <div style={{ height: "3px", background: "var(--border-color)", borderRadius: "2px", overflow: "hidden" }}>
                  {task.stage === "normalizing" && typeof task.progressPercent === "number" ? (
                    <div
                      style={{
                        height: "100%",
                        width: `${task.progressPercent}%`,
                        background: "var(--accent-primary)",
                        borderRadius: "2px",
                        transition: "width 0.4s",
                      }}
                    />
                  ) : (
                    <div className="olc-indeterminate-bar" style={{ background: "var(--accent-primary)" }} />
                  )}
                </div>
              )}
              {task.notice && (task.status === "uploading" || task.status === "processing") && (
                <span role="status" data-testid="upload-notice" style={{ color: "var(--accent-warning-text)", fontSize: "0.75rem" }}>
                  {formatNotice(t, task.notice)}
                </span>
              )}
              {task.status === "error" && task.error && (
                <span role="alert" style={{ color: "var(--accent-error-text)", fontSize: "0.78rem" }}>
                  {task.errorNotice ? formatNotice(t, task.errorNotice) : task.error}
                </span>
              )}
            </div>
          ))}

          {completed.length > 0 && (
            <button
              onClick={clearCompleted}
              style={{
                marginTop: "4px",
                alignSelf: "flex-end",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                fontSize: "0.78rem",
                padding: "4px 0",
              }}
            >
              {t("uploadManager.clearDone")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
