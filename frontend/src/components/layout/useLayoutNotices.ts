import { useCallback, useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { isPlugEvent, useStorageEvents, type StorageEvent } from "@/lib/useStorageEvents";

const UPDATE_TOAST_MS = 8000;

export type PlugNotice = "added" | "removed" | "abrupt" | null;

export function isSettingsPath(pathname: string): boolean {
  return pathname === "/settings" || pathname.startsWith("/settings/");
}

export function useUpdateNotice(pathname: string, skip: boolean) {
  const [version, setVersion] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const checkedRef = useRef(false);

  useEffect(() => {
    if (!version || dismissed || isSettingsPath(pathname)) return;
    const timer = setTimeout(() => setDismissed(true), UPDATE_TOAST_MS);
    return () => clearTimeout(timer);
  }, [version, dismissed, pathname]);

  useEffect(() => {
    if (skip || checkedRef.current) return;
    checkedRef.current = true;
    fetch(getApiUrl("/updates/check"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (d?.has_update && !d.is_downgrade) setVersion(d.latest_version ?? null);
      })
      .catch(() => {});
  }, [skip]);

  return { version, visible: Boolean(version) && !dismissed, dismiss: () => setDismissed(true) };
}

export function usePlugNotice(enabled: boolean) {
  const [plugEvent, setPlugEvent] = useState<PlugNotice>(null);
  const onStorageEvent = useCallback((event: StorageEvent) => {
    if (!isPlugEvent(event)) return;
    setPlugEvent(event.changes.includes("removed_abruptly") ? "abrupt" : event.changes.includes("removed") ? "removed" : "added");
  }, []);
  useStorageEvents(onStorageEvent, enabled);
  useEffect(() => {
    if (!plugEvent) return;
    const timer = setTimeout(() => setPlugEvent(null), 7000);
    return () => clearTimeout(timer);
  }, [plugEvent]);
  return { plugEvent, clear: () => setPlugEvent(null) };
}

export type UpdateNoticeState = ReturnType<typeof useUpdateNotice>;
export type PlugNoticeState = ReturnType<typeof usePlugNotice>;
