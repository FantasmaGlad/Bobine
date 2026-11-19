"use client";

import { useCallback, useState } from "react";

export function useTransferJobs() {
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [modes, setModes] = useState<Record<string, "import" | "index" | "export">>({});
  const onJob = useCallback((jobId: string, mode: "import" | "index") => {
    setJobIds((ids) => [...ids, jobId]);
    setModes((m) => ({ ...m, [jobId]: mode }));
  }, []);
  return { jobIds, modes, onJob };
}
