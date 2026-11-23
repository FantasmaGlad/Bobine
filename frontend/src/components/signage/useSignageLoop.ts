"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import type { DisplayChannel } from "@/lib/displayChannel";
import type { SignageEntry, SignageLoop } from "@/lib/signageLoop";
import { useServerEvent, type ServerMessage } from "@/lib/useServerEvent";

export type SignageDraft = Pick<SignageEntry, "background_id" | "seconds">;

export function useSignageLoop(channel: DisplayChannel) {
  const [entries, setEntries] = useState<SignageEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(() => fetch(getApiUrl(`/signage?channel=${channel}`), { cache: "no-store" })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<SignageLoop>;
    })
    .then((loop) => {
      setEntries(loop.items);
      setFailed(false);
    })
    .catch((error) => {
      console.warn("Boucle de visuels illisible", error);
      setFailed(true);
    }), [channel]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onChange = useCallback((message: ServerMessage) => {
    if (message.channel === channel) void reload();
  }, [channel, reload]);
  useServerEvent("signage_change", onChange);

  const save = useCallback(async (items: SignageDraft[]): Promise<boolean> => {
    const res = await fetch(getApiUrl("/signage"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, items }),
    }).catch(() => null);
    if (!res?.ok) return false;
    setEntries(((await res.json()) as SignageLoop).items);
    return true;
  }, [channel]);

  return { entries, failed, save };
}
