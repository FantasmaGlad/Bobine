import { useEffect, useState } from "react";
import { secondsLeft } from "@/lib/devices/wireless";
import { type WifiPendingChange } from "@/lib/devices/types";

export function usePendingCountdown(pending: WifiPendingChange | null, reload: () => Promise<void>) {
  const [elapsed, setElapsed] = useState(0);
  const [elapsedFor, setElapsedFor] = useState(pending);
  if (elapsedFor !== pending) {
    setElapsedFor(pending);
    setElapsed(0);
  }
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timer);
  }, [pending?.seconds_left, pending?.target, pending]);
  const left = secondsLeft(pending, elapsed);
  useEffect(() => {
    if (pending && left === 0) {
      const timer = setTimeout(() => { void reload(); }, 1500);
      return () => clearTimeout(timer);
    }
  }, [pending, left, reload]);
  return left;
}
