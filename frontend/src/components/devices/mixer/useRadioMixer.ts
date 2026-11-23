import { useState } from "react";
import { type MixerView } from "@/lib/devices/routing";
import type { RadioChannelId } from "@/lib/outputs";
import { clampMix, defaultMix, type RadioMix } from "@/lib/radioMix";
import { clampSound, type RadioSoundSettings } from "@/lib/radioSound";
import type { RadioFeed } from "@/lib/useRadioFeed";
import { type SectionProps } from "../shared/section";
import { useDevicesResource } from "../shared/useDevicesResource";
import { mergePatch, type MixPatch } from "./mixPatch";
import { useMixerWrites, type MixDrafts } from "./useMixerWrites";

export function useRadioMixer(refreshKey: number, feed: RadioFeed, notify: SectionProps["notify"], t: SectionProps["t"]) {
  const stored = useDevicesResource<MixerView>("/mixer", refreshKey);
  const [drafts, setDrafts] = useState<MixDrafts>({});
  const { pendingRef, schedule } = useMixerWrites(setDrafts, notify, t);

  const savedOf = (channel: RadioChannelId) => stored.data?.outputs.find((o) => o.channel === channel);
  const current = (channel: RadioChannelId): { mix: RadioMix; sound: RadioSoundSettings; playing: boolean } => {
    const draft = drafts[channel];
    const live = feed.channels[channel];
    const saved = savedOf(channel);
    return {
      mix: draft?.mix ?? live?.mix ?? (saved ? clampMix(saved.mix as Partial<RadioMix>) : defaultMix()),
      sound: draft?.sound ?? live?.sound ?? (saved ? clampSound(saved.sound as Partial<RadioSoundSettings>) : clampSound(null)),
      playing: live?.playing ?? saved?.playing ?? false,
    };
  };

  const patchMix = (channel: RadioChannelId, patch: MixPatch) => {
    const next = clampMix(patch as Partial<RadioMix>, current(channel).mix);
    setDrafts((d) => ({ ...d, [channel]: { ...d[channel], mix: next } }));
    const entry = pendingRef.current[channel] ?? {};
    pendingRef.current[channel] = { ...entry, mix: mergePatch(entry.mix ?? {}, patch) };
    schedule(channel);
  };

  const patchSound = (channel: RadioChannelId, sound: RadioSoundSettings) => {
    setDrafts((d) => ({ ...d, [channel]: { ...d[channel], sound } }));
    pendingRef.current[channel] = { ...pendingRef.current[channel], sound };
    schedule(channel);
  };

  return { stored, current, patchMix, patchSound };
}
