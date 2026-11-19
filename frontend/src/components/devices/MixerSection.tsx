"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import { RADIO_OUTPUTS, type MixerView, type RadioOutputId } from "@/lib/devices/routing";
import { clampMix, defaultMix, type RadioMix } from "@/lib/radioMix";
import { clampSound, type RadioSoundSettings } from "@/lib/radioSound";
import { errorText, useDevicesResource } from "./common";
import ChannelMixer from "./mixer/ChannelMixer";
import { mergePatch, type MixPatch } from "./mixer/mixPatch";
import { useMixerWrites, type MixDrafts } from "./mixer/useMixerWrites";
import type { RadioSectionProps } from "./RoutingSection";

export default function MixerSection({ refreshKey, notify, t, feed }: RadioSectionProps) {
  const stored = useDevicesResource<MixerView>("/mixer", refreshKey);
  const [drafts, setDrafts] = useState<MixDrafts>({});
  const { pendingRef, schedule } = useMixerWrites(setDrafts, notify, t);

  const savedOf = (channel: RadioOutputId) => stored.data?.outputs.find((o) => o.channel === channel);
  const current = (channel: RadioOutputId): { mix: RadioMix; sound: RadioSoundSettings } => {
    const draft = drafts[channel];
    const live = feed.channels[channel];
    const saved = savedOf(channel);
    return {
      mix: draft?.mix ?? live?.mix ?? (saved ? clampMix(saved.mix as Partial<RadioMix>) : defaultMix()),
      sound: draft?.sound ?? live?.sound ?? (saved ? clampSound(saved.sound as Partial<RadioSoundSettings>) : clampSound(null)),
    };
  };

  const patchMix = (channel: RadioOutputId, patch: MixPatch) => {
    const next = clampMix(patch as Partial<RadioMix>, current(channel).mix);
    setDrafts((d) => ({ ...d, [channel]: { ...d[channel], mix: next } }));
    const entry = pendingRef.current[channel] ?? {};
    pendingRef.current[channel] = { ...entry, mix: mergePatch(entry.mix ?? {}, patch) };
    schedule(channel);
  };

  const patchSound = (channel: RadioOutputId, sound: RadioSoundSettings, target: "music" | "announcements") => {
    if (target !== "music") return patchMix(channel, { announcements: { sound } });
    setDrafts((d) => ({ ...d, [channel]: { ...d[channel], sound } }));
    pendingRef.current[channel] = { ...pendingRef.current[channel], sound };
    schedule(channel);
  };

  if (stored.loading && !Object.keys(feed.channels).length) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (stored.error) return <div className="rl-center-note">{errorText(stored.error, t)}</div>;

  return (
    <div className="dv-section">
      <div className="dv-note">
        <Icon name="info" size={16} />
        <span>{t("devices.mixer.intro")}</span>
        {!feed.connected && <span className="dv-badge dv-badge--muted">{t("devices.mixer.offline")}</span>}
      </div>
      <div className="mx-channels">
        {RADIO_OUTPUTS.map((channel) => {
          const { mix, sound } = current(channel);
          const live = feed.channels[channel];
          return (
            <ChannelMixer
              key={channel}
              channel={channel}
              mix={mix}
              sound={sound}
              playing={live?.playing ?? savedOf(channel)?.playing ?? false}
              routeLabel={live?.route?.label ?? null}
              levels={feed.levels[channel]}
              t={t}
              onPatch={(patch) => patchMix(channel, patch)}
              onSound={(next, target) => patchSound(channel, next, target)}
            />
          );
        })}
      </div>
    </div>
  );
}
