"use client";

import { useState } from "react";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import { type StorageVolume } from "@/lib/storage/types";
import type { ShowToast } from "@/lib/useToast";
import { storageErrorText } from "./common";

type Translate = (key: string, vars?: Record<string, string | number>) => string;
export interface OpenSource { key: string; name: string; portable: boolean; volume: StorageVolume | null; }

export function useVolumeOpeners(t: Translate, lang: "fr" | "en", notify: ShowToast, reload: () => Promise<unknown>) {
  const [opening, setOpening] = useState<string | null>(null);
  const [explorer, setExplorer] = useState<OpenSource | null>(null);

  const openVolume = async (volume: StorageVolume) => {
    setOpening(volume.key);
    const result = volume.mounted ? { ok: true as const } : await storageRequest(`/volumes/${encodeKey(volume.key)}/mount`, { body: { mode: "ro" } });
    setOpening(null);
    if (!result.ok) {
      notify(storageErrorText(result.error, t, lang), "error");
      void reload();
      return;
    }
    setExplorer({ key: volume.key, name: volume.name, portable: false, volume });
    if (!volume.mounted) void reload();
  };

  const openPortable = async (id: string, name: string) => {
    setOpening(id);
    const result = await storageRequest(`/portable/${encodeKey(id)}/mount`, { body: {} });
    setOpening(null);
    if (!result.ok) {
      notify(storageErrorText(result.error, t, lang), "error");
      void reload();
      return;
    }
    setExplorer({ key: id, name, portable: true, volume: null });
  };

  return { opening, explorer, setExplorer, openVolume, openPortable };
}
