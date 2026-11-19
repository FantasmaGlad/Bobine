"use client";

import { useState } from "react";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import { type Health, type LongevitySettings, type StorageVolume } from "@/lib/storage/types";
import { storageErrorText, type StorageCtx } from "../common";

type Result = { ok: boolean; error?: Parameters<typeof storageErrorText>[0] };

export function useVolumeActions(volume: StorageVolume | null, { t, lang, notify }: StorageCtx, onChanged: () => void, onClose: () => void) {
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  const key = volume ? encodeKey(volume.key) : "";

  const run = async (action: () => Promise<Result>, ok?: string) => {
    setBusy(true);
    const result = await action();
    setBusy(false);
    if (result.ok) {
      if (ok) notify(ok, "success");
      onChanged();
    } else if (result.error) notify(storageErrorText(result.error, t, lang), "error");
  };

  const setSetting = (values: Partial<LongevitySettings>) =>
    run(async () => storageRequest(`/volumes/${key}/settings`, { method: "PUT", body: values }));
  const eject = () =>
    run(async () => {
      const result = await storageRequest(`/volumes/${key}/eject`, { body: {} });
      if (result.ok) {
        notify(t("storage.ejected", { name: volume?.name ?? "" }), "success");
        onClose();
      }
      return result;
    });
  const stopExtension = () =>
    run(async () => {
      const result = await storageRequest(`/volumes/${key}/library?purge=true`, { method: "DELETE" });
      if (result.ok) {
        setConfirmStop(false);
        notify(t("storage.extension.stopped"), "success");
      }
      return result;
    });
  const refreshHealth = async () => {
    setBusy(true);
    const result = await storageRequest<Health>(`/volumes/${key}/health?refresh=true`);
    setBusy(false);
    if (result.ok) setHealth(result.data);
    else notify(storageErrorText(result.error, t, lang), "error");
  };

  return { busy, health, confirmStop, setConfirmStop, setSetting, eject, stopExtension, refreshHealth };
}
