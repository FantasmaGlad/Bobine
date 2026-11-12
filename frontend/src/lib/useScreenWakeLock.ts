"use client";

import { useEffect, useRef } from "react";

const WAKE_LOCK_RETRY_MS = 15_000;

export function useScreenWakeLock(enabled: boolean) {
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!enabled || typeof navigator === "undefined" || !("wakeLock" in navigator)) {
      return;
    }

    let isActive = true;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const retryLater = () => {
      if (!isActive || retryTimer) return;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        requestWakeLock();
      }, WAKE_LOCK_RETRY_MS);
    };

    const requestWakeLock = async () => {
      try {
        if (document.visibilityState !== "visible") return;
        if (wakeLockRef.current && !wakeLockRef.current.released) return;

        // eslint-disable-next-line compat/compat -- détectée par feature detection
        const sentinel = await navigator.wakeLock.request("screen");
        if (!isActive) {
          await sentinel.release();
          return;
        }

        wakeLockRef.current = sentinel;
        sentinel.addEventListener("release", () => {
          if (wakeLockRef.current === sentinel) {
            wakeLockRef.current = null;
          }
          retryLater();
        });
      } catch {
        retryLater();
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        requestWakeLock();
      }
    };

    requestWakeLock();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      isActive = false;
      if (retryTimer) clearTimeout(retryTimer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (wakeLockRef.current) {
        wakeLockRef.current.release().catch(() => {});
        wakeLockRef.current = null;
      }
    };
  }, [enabled]);
}
