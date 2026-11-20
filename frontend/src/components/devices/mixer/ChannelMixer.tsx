"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import RadioSoundPanel from "@/components/RadioSoundPanel";
import { type RadioOutputId } from "@/lib/devices/routing";
import { hasSolo, type MeterId, type RadioMix, type StripId } from "@/lib/radioMix";
import { clampSound, type RadioSoundSettings } from "@/lib/radioSound";
import type { FeedLevels } from "@/lib/useRadioFeed";
import { type SectionProps } from "../shared/section";
import { type MixPatch } from "./mixPatch";
import Strip from "./MixerStrip";

type T = SectionProps["t"];
type OnSound = (sound: RadioSoundSettings, target: "music" | "announcements") => void;

interface EqProps {
  id: StripId;
  current: RadioSoundSettings;
  openEq: StripId | null;
  setOpenEq: (id: StripId | null) => void;
  onSound: OnSound;
  t: T;
}

function StripEq({ id, current, openEq, setOpenEq, onSound, t }: EqProps) {
  return (
    <div className="mx-eq">
      <button type="button" className="dv-link-btn" aria-expanded={openEq === id} onClick={() => setOpenEq(openEq === id ? null : id)}>
        <Icon name={openEq === id ? "expand_less" : "tune"} size={14} /> {t("devices.mixer.equalizer")}
      </button>
      {openEq === id && (
        <RadioSoundPanel
          sound={current}
          sendCommand={(command, params) => { if (command === "radio_set_sound") onSound(clampSound(params?.sound as RadioSoundSettings, current), id); }}
        />
      )}
    </div>
  );
}

interface ChannelProps {
  channel: RadioOutputId;
  mix: RadioMix;
  sound: RadioSoundSettings;
  playing: boolean;
  routeLabel: string | null;
  levels: FeedLevels | undefined;
  t: T;
  onPatch: (patch: MixPatch) => void;
  onSound: OnSound;
}

function ChannelHead({ channel, playing, routeLabel, solo, onPatch, t }: ChannelProps & { solo: boolean }) {
  return (
    <header className="mx-channel-head">
      <span className="dv-icon"><Icon name="radio" size={22} /></span>
      <span className="dv-text">
        <span className="dv-title">
          {t(`devices.map.channels.${channel}`)}
          <span className={`dv-badge${playing ? "" : " dv-badge--muted"}`}>{playing ? t("devices.routing.playing") : t("devices.routing.stopped")}</span>
        </span>
        <span className="dv-sub">{routeLabel ? t("devices.mixer.routedTo", { name: routeLabel }) : t("devices.routing.defaultOutput")}</span>
      </span>
      {solo && (
        <button type="button" className="btn btn-secondary" onClick={() => onPatch({ music: { solo: false }, announcements: { solo: false } })}>
          <Icon name="headset_off" size={14} /> {t("devices.mixer.soloClear")}
        </button>
      )}
    </header>
  );
}

export default function ChannelMixer(props: ChannelProps) {
  const { channel, mix, sound, playing, levels, t, onPatch, onSound } = props;
  const [openEq, setOpenEq] = useState<StripId | null>(null);
  const solo = hasSolo(mix);
  const level = (id: MeterId) => (playing ? levels?.[id] : 0);
  const eq = { openEq, setOpenEq, onSound, t };
  return (
    <section className="mx-channel glass-interactive" aria-label={t(`devices.map.channels.${channel}`)} data-focus-id={channel}>
      <ChannelHead {...props} solo={solo} />
      {solo && <p className="dv-note"><Icon name="info" size={16} /><span>{t("devices.mixer.soloActive")}</span></p>}
      <div className="mx-strips">
        <Strip
          id="music" t={t} gain={mix.music.gain_db} muted={mix.music.muted} solo={mix.music.solo}
          silencedBySolo={solo && !mix.music.solo} level={level("music")}
          onGain={(db) => onPatch({ music: { gain_db: db } })}
          onMute={() => onPatch({ music: { muted: !mix.music.muted } })}
          onSolo={() => onPatch({ music: { solo: !mix.music.solo } })}
        ><StripEq id="music" current={sound} {...eq} /></Strip>
        <Strip
          id="announcements" t={t} gain={mix.announcements.gain_db} muted={mix.announcements.muted} solo={mix.announcements.solo}
          silencedBySolo={solo && !mix.announcements.solo} level={level("announcements")}
          onGain={(db) => onPatch({ announcements: { gain_db: db } })}
          onMute={() => onPatch({ announcements: { muted: !mix.announcements.muted } })}
          onSolo={() => onPatch({ announcements: { solo: !mix.announcements.solo } })}
        ><StripEq id="announcements" current={mix.announcements.sound} {...eq} /></Strip>
        <Strip
          id="master" t={t} gain={mix.master.gain_db} muted={mix.master.muted}
          silencedBySolo={false} level={level("master")}
          onGain={(db) => onPatch({ master: { gain_db: db } })}
          onMute={() => onPatch({ master: { muted: !mix.master.muted } })}
        />
      </div>
    </section>
  );
}
