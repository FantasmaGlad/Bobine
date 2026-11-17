import { useEffect, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import { formatFinished, type FormatJob } from "@/lib/storage/format";
import { encodeKey, storageRequest } from "@/lib/storage/request";

const POLL_MS = 700;

interface FormatJobPolling {
  active: boolean;
  job: FormatJob | null;
  setJob: Dispatch<SetStateAction<FormatJob | null>>;
  setPollError: (value: boolean) => void;
  onResult: () => void;
  finished: MutableRefObject<boolean>;
  onChanged: () => void;
}

export function useFormatJobPolling({ active, job, setJob, setPollError, onResult, finished, onChanged }: FormatJobPolling) {
  const changed = useRef(onChanged);
  useEffect(() => {
    changed.current = onChanged;
  }, [onChanged]);

  useEffect(() => {
    if (!active || !job) return;
    const jobId = job.job_id;
    const timer = setInterval(async () => {
      const result = await storageRequest<FormatJob>(`/format/jobs/${encodeKey(jobId)}`);
      if (!result.ok) {
        setPollError(true);
        if (result.error.status === 404) {
          setJob({ ...job, state: "failed", outcome: "unverified", can_cancel: false, error: { code: "format_job_not_found", message: "" } });
          onResult();
        }
        return;
      }
      setPollError(false);
      setJob(result.data);
      if (formatFinished(result.data) && !finished.current) {
        finished.current = true;
        onResult();
        changed.current();
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [active, job, setJob, setPollError, onResult, finished]);
}
