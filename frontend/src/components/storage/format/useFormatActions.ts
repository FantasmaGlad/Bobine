"use client";

import { useCallback, useRef, useState } from "react";
import { needsNewPlan, refusalKey, type FormatFs, type FormatJob, type FormatPlan } from "@/lib/storage/format";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import type { ApiError } from "@/lib/apiError";
import { storageErrorText, tr, type StorageCtx } from "../common";
import { useFormatJobPolling } from "./useFormatJobPolling";
import type { Stage } from "./useFormatPlan";

interface Inputs {
  targetKey: string;
  resume: FormatJob | null | undefined;
  stage: Stage;
  setStage: (stage: Stage) => void;
  setRefusal: (error: ApiError) => void;
  plan: FormatPlan | null;
  fs: FormatFs | null;
  label: string;
  typed: string;
  acknowledged: boolean;
  ctx: StorageCtx;
  onChanged: () => void;
}

export function useFormatActions({ targetKey, resume, stage, setStage, setRefusal, plan, fs, label, typed, acknowledged, ctx, onChanged }: Inputs) {
  const { t, lang, notify } = ctx;
  const [busy, setBusy] = useState(false);
  const [pollError, setPollError] = useState(false);
  const [job, setJob] = useState<FormatJob | null>(resume ?? null);
  const finished = useRef(false);
  const showResult = useCallback(() => setStage("result"), [setStage]);
  useFormatJobPolling({ active: stage === "running", job, setJob, setPollError, onResult: showResult, finished, onChanged });
  const refusalText = (error: ApiError) => tr(t, refusalKey(error.code), storageErrorText(error, t, lang), { package: String(error.extra.package ?? "") });

  const execute = async () => {
    if (!plan || !fs) return;
    setBusy(true);
    const result = await storageRequest<{ job_id: string }>("/format/execute", {
      body: { key: targetKey, token: plan.token, fs, label: label.trim(), confirm: typed, acknowledged },
    });
    setBusy(false);
    if (result.ok) {
      finished.current = false;
      const first = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(result.data.job_id)}`);
      setJob(first.ok ? first.data : { job_id: result.data.job_id, state: "running", steps: [], stage: "starting", outcome: null, percent: 0, can_cancel: true, point_of_no_return: false, error: null, report: null, fs, label });
      setStage("running");
      return;
    }
    if (needsNewPlan(result.error.code) || result.error.code === "format_not_found") {
      setRefusal(result.error);
      setStage("refused");
    } else {
      notify(refusalText(result.error), "error");
    }
  };

  const cancel = async () => {
    if (!job) return;
    const result = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(job.job_id)}`, { method: "DELETE" });
    if (result.ok) setJob(result.data);
    else notify(refusalText(result.error), "error");
  };

  return { busy, setBusy, pollError, job, execute, cancel, refusalText };
}
