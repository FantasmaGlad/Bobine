"use client";

import { useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { importJobsUrl } from "@/lib/storage/request";
import { isFinished, jobPercent } from "@/lib/storage/display";
import { type ImportJob } from "@/lib/storage/types";
import { tr, type StorageCtx } from "./common";

interface Props extends StorageCtx {
  jobIds: string[];
  modes: Record<string, "import" | "index" | "export">;
  onDone: () => void;
}

async function fetchJobs(): Promise<ImportJob[]> {
  try {
    const res = await fetch(importJobsUrl(), { cache: "no-store", credentials: "include" });
    return res.ok ? ((await res.json()) as ImportJob[]) : [];
  } catch {
    return [];
  }
}
function useImportJobs(jobIds: string[], onDone: () => void) {
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);
  const finishedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (jobIds.length === 0) return;
    let cancelled = false;
    const tick = async () => {
      const all = await fetchJobs();
      if (cancelled) return;
      const mine = all.filter((j) => jobIds.includes(j.id));
      setJobs(mine);
      for (const job of mine) {
        if (isFinished(job) && !finishedRef.current.has(job.id)) {
          finishedRef.current.add(job.id);
          doneRef.current();
        }
      }
    };
    void tick();
    const timer = setInterval(tick, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [jobIds]);
  return jobs;
}

function jobSummary(job: ImportJob, finished: boolean, t: StorageCtx["t"]) {
  const details = job.details ?? {};
  const added = details.imported ?? details.indexed ?? details.exported ?? 0;
  const failed = details.failed?.length ?? 0;
  const skipped = details.skipped?.length ?? 0;
  if (job.stage === "error") return t("storage.job.error", { message: job.error ?? "" });
  if (job.stage === "cancelled") return t("storage.job.cancelled");
  if (!finished) return "";
  const parts = [added ? t("storage.job.done", { count: added }) : t("storage.job.doneNone")];
  if (skipped) parts.push(t("storage.job.skipped", { count: skipped }));
  if (failed) parts.push(t("storage.job.failed", { count: failed }));
  return parts.join(" · ");
}

async function cancelJob(id: string) {
  try {
    await fetch(`${importJobsUrl()}/${id}`, { method: "DELETE", credentials: "include" });
  } catch {
  }
}

function JobRow({ job, mode, t }: { job: ImportJob; mode: "import" | "index" | "export"; t: StorageCtx["t"] }) {
        const finished = isFinished(job);
        const percent = jobPercent(job);
        const verb = t(mode === "index" ? "storage.job.indexing" : mode === "export" ? "storage.job.exporting" : "storage.job.importing", {
          done: Math.min((job.files_done ?? 0) + (finished ? 0 : 1), job.files_total ?? 0),
          total: job.files_total ?? 0,
        });
        const details = job.details ?? {};
  const summary = jobSummary(job, finished, t);
  return (
    <div className="dv-row glass-interactive">
      <span className="dv-icon"><Icon name={finished ? (job.stage === "done" ? "task_alt" : "error") : "sync"} size={22} className={finished ? "" : "olc-spin"} /></span>
      <span className="dv-text">
        <span className="dv-title">{finished ? summary : verb}</span>
        <span className="dv-sub">
          {finished
            ? details.skipped?.slice(0, 2).map((s) => tr(t, `storage.job.reasons.${s.reason}`, s.reason)).join(" · ")
            : job.current_file ?? ""}
        </span>
        {!finished && (
          <span className="st-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined}>
            <span style={{ transform: `scaleX(${(percent ?? 8) / 100})` }} />
          </span>
        )}
      </span>
      {!finished && (
        <span className="dv-actions">
          <button type="button" className="btn btn-secondary" onClick={() => cancelJob(job.id)}>{t("storage.job.cancel")}</button>
        </span>
      )}
    </div>
  );
}

export default function TransferStatus({ jobIds, modes, onDone, t }: Props) {
  const jobs = useImportJobs(jobIds, onDone);
  if (jobs.length === 0) return null;
  return (
    <div className="dv-list" role="status" aria-live="polite">
      {jobs.map((job) => <JobRow key={job.id} job={job} mode={modes[job.id] ?? "import"} t={t} />)}
    </div>
  );
}
