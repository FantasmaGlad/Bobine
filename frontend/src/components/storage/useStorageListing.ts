"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { type DevicesStatus } from "@/lib/devices/types";
import { diffVolumes } from "@/lib/storage/display";
import { storageRequest } from "@/lib/storage/request";
import { type PortableListing, type StorageVolume, type VolumeListing } from "@/lib/storage/types";
import type { ShowToast } from "@/lib/useToast";
import { storageErrorText } from "./common";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function useStorageListing(t: Translate, lang: "fr" | "en", notify: ShowToast) {
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [listing, setListing] = useState<VolumeListing | null>(null);
  const [portable, setPortable] = useState<PortableListing | null>(null);
  const previous = useRef<StorageVolume[] | null>(null);

  const loadStatus = useCallback(() => devicesRequest<DevicesStatus>("/status").then((result) => {
    if (result.ok) {
      setStatus(result.data);
      setLoadError(false);
    } else {
      setLoadError(true);
    }
  }), []);
  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const reload = useCallback(() => Promise.all([storageRequest<VolumeListing>("/volumes"), storageRequest<PortableListing>("/portable")]).then(([volumes, phones]) => {
    if (volumes.ok) {
      const before = previous.current;
      previous.current = volumes.data.volumes;
      setListing(volumes.data);
      if (before) {
        const abrupt = new Set(volumes.data.recent_removals.filter((r) => r.abrupt).map((r) => r.key));
        const diff = diffVolumes(before, volumes.data.volumes, abrupt);
        const removed = diff.removed[0];
        if (removed?.abrupt) notify(t("storage.abrupt", { name: removed.name }), "warning");
        else if (removed) notify(t("storage.unplugged", { name: removed.name }), "success");
        else if (diff.added[0]) notify(t("storage.plugged", { name: diff.added[0] }), "success");
      }
    } else {
      notify(storageErrorText(volumes.error, t, lang), "error");
    }
    if (phones.ok) setPortable(phones.data);
  }), [notify, t, lang]);

  useEffect(() => {
    if (!status) return;
    void reload();
  }, [status, reload]);

  return { status, loadError, listing, portable, reload };
}
