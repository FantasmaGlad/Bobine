import { useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { errorText, type SectionProps } from "../common";

export type AudioCall = (path: string, body: unknown, okMessage?: string) => Promise<void>;

export function useAudioCalls(notify: SectionProps["notify"], t: SectionProps["t"], reload: () => Promise<void>) {
  const [draft, setDraft] = useState<Record<string, number>>({});

  const call: AudioCall = async (path, body, okMessage) => {
    const result = await devicesRequest(path, { body });
    if (result.ok) {
      if (okMessage) notify(okMessage, "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };

  const commitVolume = async (id: string, percent: number) => {
    await call("/audio/volume", { id, volume: percent / 100 });
    setDraft((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
  };

  return { draft, setDraft, call, commitVolume };
}

export type AudioCalls = ReturnType<typeof useAudioCalls>;
