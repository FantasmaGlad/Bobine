import { useCallback, useEffect, useState } from "react";
import { getDevicesApiUrl } from "@/lib/devices/request";
import { clampSound, defaultSound, type RadioSoundSettings } from "@/lib/radioSound";
import { type SectionProps } from "../shared/section";

export const VIDEO_CHANNELS = ["cable", "network"] as const;
export type VideoChannel = (typeof VIDEO_CHANNELS)[number];

function playbackUrl(path: string): string {
  return getDevicesApiUrl("").replace(/\/devices$/, "") + path;
}

export function useVideoSound(refreshKey: number, notify: SectionProps["notify"], t: SectionProps["t"]) {
  const [sounds, setSounds] = useState<Record<VideoChannel, RadioSoundSettings>>({ cable: defaultSound(), network: defaultSound() });

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      VIDEO_CHANNELS.map((c) =>
        fetch(playbackUrl(`/playback/state?channel=${c}`), { cache: "no-store" })
          .then((res) => (res.ok ? res.json() : null))
          .then((state) => [c, clampSound(state?.sound)] as const)
          .catch(() => [c, defaultSound()] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setSounds(Object.fromEntries(entries) as Record<VideoChannel, RadioSoundSettings>);
    });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const save = useCallback((channel: VideoChannel, sound: RadioSoundSettings) => {
    setSounds((prev) => ({ ...prev, [channel]: sound }));
    fetch(playbackUrl(`/playback/${channel}/set_sound`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sound }),
    })
      .then((res) => { if (!res.ok) throw new Error(String(res.status)); })
      .catch(() => notify(t("devices.videoSound.saveFailed"), "error"));
  }, [notify, t]);

  return { sounds, save };
}
