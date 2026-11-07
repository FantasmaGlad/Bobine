"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import RadioSoundPanel from "@/components/RadioSoundPanel";
import SegmentedTabs from "@/components/SegmentedTabs";
import { clampSound, defaultSound, type RadioSoundSettings } from "@/lib/radioSound";
import { getDevicesApiUrl } from "@/lib/devicesApi";
import type { SectionProps } from "./common";

/** Canaux vidéo dont le son se règle ici ; la radio garde sa table de mixage. */
const CHANNELS = ["cable", "network"] as const;
type VideoChannel = (typeof CHANNELS)[number];

function playbackUrl(path: string): string {
  // `getDevicesApiUrl` fixe l'hôte de développement (port 3000) ; on retire son suffixe pour viser /api/playback.
  return getDevicesApiUrl("").replace(/\/devices$/, "") + path;
}

/** Égaliseur, basses, loudness et limiteur de chaque canal vidéo (câblé, réseau), appliqués par le lecteur du canal. */
export default function VideoSoundSection({ refreshKey, notify, t }: SectionProps) {
  const [sounds, setSounds] = useState<Record<VideoChannel, RadioSoundSettings>>({ cable: defaultSound(), network: defaultSound() });
  const [channel, setChannel] = useState<VideoChannel>("cable");

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      CHANNELS.map((c) =>
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

  const send = useCallback((command: string, params?: Record<string, unknown>) => {
    if (command !== "radio_set_sound") return;
    const sound = clampSound(params?.sound as RadioSoundSettings, sounds[channel]);
    setSounds((prev) => ({ ...prev, [channel]: sound }));
    fetch(playbackUrl(`/playback/${channel}/set_sound`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sound }),
    })
      .then((res) => { if (!res.ok) throw new Error(String(res.status)); })
      .catch(() => notify(t("devices.videoSound.saveFailed"), "error"));
  }, [channel, sounds, notify, t]);

  return (
    <section className="mx-channel glass-interactive" aria-label={t("devices.videoSound.title")}>
      <header className="mx-channel-head">
        <span className="dv-icon"><Icon name="graphic_eq" size={22} /></span>
        <span className="dv-text">
          <span className="dv-title">{t("devices.videoSound.title")}</span>
          <span className="dv-sub">{t("devices.videoSound.intro")}</span>
        </span>
      </header>
      <SegmentedTabs
        ariaLabel={t("devices.videoSound.title")}
        value={channel}
        onChange={(id) => setChannel(id as VideoChannel)}
        tabs={CHANNELS.map((c) => ({ id: c, label: t(`devices.map.channels.${c}`) }))}
      />
      <RadioSoundPanel key={channel} sound={sounds[channel]} sendCommand={send} />
    </section>
  );
}
