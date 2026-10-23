"use client";

import { useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { importJobsUrl, isFinished, jobPercent, type ImportJob } from "@/lib/storageApi";
import { tr, type StorageCtx } from "./common";

interface Props extends StorageCtx {
  /** Identifiants des travaux lancés depuis cette page (import, ajout à la bibliothèque, export). */
  jobIds: string[];
  /** Nature de chaque travail pour choisir le verbe (« Import », « Ajout »). */
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

/** Avancement des travaux en cours : une barre, un verbe, un bilan ; l'annulation passe par la file d'import commune. */
export default function TransferStatus({ jobIds, modes, onDone, t }: Props) {
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

  const cancel = async (id: string) => {
    try {
      await fetch(`${importJobsUrl()}/${id}`, { method: "DELETE", credentials: "include" });
    } catch {
      /* annulation best-effort */
    }
  };

  if (jobs.length === 0) return null;
  return (
    <div className="dv-list" role="status" aria-live="polite">
      {jobs.map((job) => {
        const finished = isFinished(job);
        const percent = jobPercent(job);
        const mode = modes[job.id] ?? "import";
        const verb = t(mode === "index" ? "storage.job.indexing" : mode === "export" ? "storage.job.exporting" : "storage.job.importing", {
          done: Math.min((job.files_done ?? 0) + (finished ? 0 : 1), job.files_total ?? 0),
          total: job.files_total ?? 0,
        });
        const details = job.details ?? {};
        const added = details.imported ?? details.indexed ?? details.exported ?? 0;
        const failed = details.failed?.length ?? 0;
        const skipped = details.skipped?.length ?? 0;
        let summary = "";
        if (job.stage === "error") summary = t("storage.job.error", { message: job.error ?? "" });
        else if (job.stage === "cancelled") summary = t("storage.job.cancelled");
        else if (finished) {
          const parts = [added ? t("storage.job.done", { count: added }) : t("storage.job.doneNone")];
          if (skipped) parts.push(t("storage.job.skipped", { count: skipped }));
          if (failed) parts.push(t("storage.job.failed", { count: failed }));
          summary = parts.join(" · ");
        }
        return (
          <div key={job.id} className="dv-row glass-interactive">
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
                  <span style={{ width: `${percent ?? 8}%` }} />
                </span>
              )}
            </span>
            {!finished && (
              <span className="dv-actions">
                <button type="button" className="btn btn-secondary" onClick={() => cancel(job.id)}>{t("storage.job.cancel")}</button>
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
