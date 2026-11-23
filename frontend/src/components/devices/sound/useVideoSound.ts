import { useCallback, useEffect, useState } from "react";
import { getDevicesApiUrl } from "@/lib/devices/request";
import { OUTPUT_IDS, type OutputId } from "@/lib/outputs";
import { clampSound, defaultSound, type RadioSoundSettings } from "@/lib/radioSound";
import { type SectionProps } from "../shared/section";


function playbackUrl(path: string): string {
  return getDevicesApiUrl("").replace(/\/devices$/, "") + path;
}

export function useVideoSound(refreshKey: number, notify: SectionProps["notify"], t: SectionProps["t"]) {
  const [sounds, setSounds] = useState<Record<OutputId, RadioSoundSettings>>({ cable: defaultSound(), network: defaultSound() });

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      OUTPUT_IDS.map((c) =>
        fetch(playbackUrl(`/playback/state?channel=${c}`), { cache: "no-store" })
          .then((res) => (res.ok ? res.json() : null))
          .then((state) => [c, clampSound(state?.sound)] as const)
          .catch(() => [c, defaultSound()] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setSounds(Object.fromEntries(entries) as Record<OutputId, RadioSoundSettings>);
    });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const save = useCallback((channel: OutputId, sound: RadioSoundSettings) => {
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
