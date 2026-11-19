"use client";

import { useCallback, useEffect, useState } from "react";
import { defaultFormat, formatTravels, type FormatFs, type FormatPlan } from "@/lib/storage/format";
import { storageRequest } from "@/lib/storage/request";
import type { ApiError } from "@/lib/apiError";

export type Stage = "loading" | "refused" | "choose" | "confirm" | "running" | "result";

export function useFormatPlan(targetKey: string, resuming: boolean) {
  const [stage, setStage] = useState<Stage>(resuming ? "running" : "loading");
  const [plan, setPlan] = useState<FormatPlan | null>(null);
  const [refusal, setRefusal] = useState<ApiError | null>(null);
  const [windowsOrMac, setWindowsOrMac] = useState(false);
  const [fs, setFs] = useState<FormatFs | null>(null);
  const [label, setLabel] = useState("");

  const fetchPlan = useCallback((travels: boolean) => storageRequest<FormatPlan>("/format/plan", { body: { key: targetKey, travels: formatTravels(travels) } }).then((result) => {
    if (!result.ok) {
      setRefusal(result.error);
      setStage("refused");
      return;
    }
    setPlan(result.data);
    const chosen = defaultFormat(result.data);
    setFs(chosen);
    setLabel(result.data.options.find((o) => o.fs === chosen)?.label ?? "BOBINE");
    setStage("choose");
  }), [targetKey]);

  const loadPlan = useCallback((travels: boolean) => {
    setStage("loading");
    return fetchPlan(travels);
  }, [fetchPlan]);

  useEffect(() => {
    if (!resuming) {
      void fetchPlan(false);
    }
  }, [fetchPlan, resuming]);

  return { stage, setStage, plan, refusal, setRefusal, windowsOrMac, setWindowsOrMac, fs, setFs, label, setLabel, loadPlan };
}
