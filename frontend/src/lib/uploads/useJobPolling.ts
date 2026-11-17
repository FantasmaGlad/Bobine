import { useEffect, useRef, type MutableRefObject } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { translate } from "@/lib/i18n";
import { isJobLost, isServerSilent, nextMissCount, nextPollFailures } from "@/lib/uploadFlow";
import { jobPatch } from "./jobPatch";
import type { ImportJobStatus, UploadTask } from "./types";

const JOB_POLL_INTERVAL_MS = 1500;

type Update = (id: string, patch: Partial<UploadTask>) => void;

function applyMissing(task: UploadTask, misses: Map<string, number>, update: Update) {
  const missCount = nextMissCount(misses.get(task.id), false);
  misses.set(task.id, missCount);
  if (isJobLost(missCount)) {
    misses.delete(task.id);
    update(task.id, {
      status: "error",
      error: translate("uploadManager.taskLost"),
      errorNotice: { key: "uploads.errors.jobLost" },
      notice: null,
      queuePosition: null,
    });
  } else if (task.notice) {
    update(task.id, { notice: null });
  }
}

function applyJobs(jobs: ImportJobStatus[], processing: UploadTask[], misses: Map<string, number>, update: Update, remove: (id: string) => void) {
  const byId = new Map(jobs.map((j) => [j.id, j]));
  const stillProcessing = new Set(processing.map((t) => t.id));
  for (const id of [...misses.keys()]) if (!stillProcessing.has(id)) misses.delete(id);
  processing.forEach((task) => {
    const job = task.jobId ? byId.get(task.jobId) : undefined;
    if (!job) {
      applyMissing(task, misses, update);
      return;
    }
    misses.delete(task.id);
    if (task.notice) update(task.id, { notice: null });
    const patch = jobPatch(job);
    if (patch === "remove") remove(task.id);
    else update(task.id, patch);
  });
}

export function useJobPolling(uploadsRef: MutableRefObject<UploadTask[]>, update: Update, remove: (id: string) => void) {
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
        .then((jobs: ImportJobStatus[]) => {
          pollFailuresRef.current = nextPollFailures(pollFailuresRef.current, true);
          applyJobs(jobs, processing, missCountsRef.current, update, remove);
        })
        .catch(() => {
          pollFailuresRef.current = nextPollFailures(pollFailuresRef.current, false);
          if (!isServerSilent(pollFailuresRef.current)) return;
          processing.forEach((task) => {
            if (task.notice?.key !== "uploads.serverUnreachable") {
              update(task.id, { notice: { key: "uploads.serverUnreachable" } });
            }
          });
        });
    }, JOB_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [uploadsRef, update, remove]);
}
