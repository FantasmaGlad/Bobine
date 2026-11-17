import type { UploadTask } from "./types";

const PROGRESS_MIN_INTERVAL_MS = 250;

export function progressReporter(update: (patch: Partial<UploadTask>) => void, now: () => number = Date.now) {
  const startTime = now();
  let lastUpdateAt = 0;
  return (loaded: number, total: number) => {
    if (total <= 0) return;
    const at = now();
    if (loaded < total && lastUpdateAt !== 0 && at - lastUpdateAt < PROGRESS_MIN_INTERVAL_MS) return;
    lastUpdateAt = at;
    const elapsedSec = (at - startTime) / 1000;
    let uploadEtaSeconds: number | null = null;
    if (elapsedSec > 0.5 && loaded > 0) {
      uploadEtaSeconds = Math.max(0, Math.round((total - loaded) / (loaded / elapsedSec)));
    }
    update({ progress: Math.round((loaded / total) * 100), uploadEtaSeconds });
  };
}
