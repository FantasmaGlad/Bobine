"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import RadioSoundPanel from "@/components/RadioSoundPanel";
import { devicesRequest, RADIO_OUTPUTS, type MixerView, type RadioOutputId } from "@/lib/devicesApi";
import { clampMix, defaultMix, formatDb, GAIN_MAX_DB, GAIN_MIN_DB, hasSolo, type MeterId, type RadioMix, type StripId } from "@/lib/radioMix";
import { clampSound, type RadioSoundSettings } from "@/lib/radioSound";
import type { FeedLevels } from "@/lib/useRadioFeed";
import { errorText, useDevicesResource } from "./common";
import type { RadioSectionProps } from "./RoutingSection";

/** Délai avant d'envoyer le dernier réglage pendant un glissement (une écriture par pause, pas par pas de curseur). */
const SEND_DELAY_MS = 150;

type MixPatch = { master?: Partial<RadioMix["master"]>; music?: Partial<RadioMix["music"]>; announcements?: Partial<RadioMix["announcements"]> };

function mergePatch(a: MixPatch, b: MixPatch): MixPatch {
  return { master: { ...a.master, ...b.master }, music: { ...a.music, ...b.music }, announcements: { ...a.announcements, ...b.announcements } };
}

/** Vumètre : longueur proportionnelle au niveau crête (dBFS −60…0), repères de zone par la couleur ET la valeur lue. */
function MeterBar({ level, label }: { level: number | undefined; label: string }) {
  const value = level ?? 0;
  return (
    <div className="mx-meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
      <div className={`mx-meter-fill${value >= 92 ? " is-hot" : ""}`} style={{ width: `${value}%` }} />
    </div>
  );
}

interface StripProps {
  id: StripId | "master";
  t: RadioSectionProps["t"];
  gain: number;
  muted: boolean;
  solo?: boolean;
  /** Coupée parce qu'une autre tranche est en solo. */
  silencedBySolo: boolean;
  level: number | undefined;
  onGain: (db: number) => void;
  onMute: () => void;
  onSolo?: () => void;
  children?: React.ReactNode;
}

function Strip({ id, t, gain, muted, solo, silencedBySolo, level, onGain, onMute, onSolo, children }: StripProps) {
  const name = t(`devices.mixer.strips.${id}`);
  return (
    <div className={`mx-strip glass-interactive${muted || silencedBySolo ? " is-silent" : ""}`} data-strip={id}>
      <div className="mx-strip-head">
        <span className="dv-title">{name}</span>
        {silencedBySolo && <span className="dv-badge dv-badge--muted">{t("devices.mixer.silencedBySolo")}</span>}
      </div>
      <MeterBar level={level} label={t("devices.mixer.meter", { name })} />
      <label className="mx-fader">
        <span className="mx-fader-label">{t("devices.mixer.level")}</span>
        <input
          type="range"
          min={GAIN_MIN_DB}
          max={GAIN_MAX_DB}
          step={1}
          value={gain}
          aria-label={`${name} — ${t("devices.mixer.level")}`}
          onChange={(e) => onGain(Number(e.target.value))}
        />
        <span className="dv-value">{formatDb(gain)}</span>
      </label>
      <div className="mx-toggles">
        <button type="button" className={`mx-toggle mx-toggle--mute${muted ? " is-on" : ""}`} aria-pressed={muted} onClick={onMute}>
          <Icon name={muted ? "volume_off" : "volume_up"} size={16} /> {muted ? t("devices.audio.unmute") : t("devices.audio.mute")}
        </button>
        {onSolo && (
          <button type="button" className={`mx-toggle mx-toggle--solo${solo ? " is-on" : ""}`} aria-pressed={!!solo} onClick={onSolo}>
            <Icon name="headphones" size={16} /> {t("devices.mixer.solo")}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function ChannelMixer({ channel, mix, sound, playing, routeLabel, levels, t, onPatch, onSound }: {
  channel: RadioOutputId;
  mix: RadioMix;
  sound: RadioSoundSettings;
  playing: boolean;
  routeLabel: string | null;
  levels: FeedLevels | undefined;
  t: RadioSectionProps["t"];
  onPatch: (patch: MixPatch) => void;
  onSound: (sound: RadioSoundSettings, target: "music" | "announcements") => void;
}) {
  const [openEq, setOpenEq] = useState<StripId | null>(null);
  const solo = hasSolo(mix);
  const level = (id: MeterId) => (playing ? levels?.[id] : 0);
  const eq = (id: StripId, current: RadioSoundSettings) => (
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
  return (
    <section className="mx-channel glass-interactive" aria-label={t(`devices.map.channels.${channel}`)} data-focus-id={channel}>
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
      {solo && <p className="dv-note"><Icon name="info" size={16} /><span>{t("devices.mixer.soloActive")}</span></p>}
      <div className="mx-strips">
        <Strip
          id="music" t={t} gain={mix.music.gain_db} muted={mix.music.muted} solo={mix.music.solo}
          silencedBySolo={solo && !mix.music.solo} level={level("music")}
          onGain={(db) => onPatch({ music: { gain_db: db } })}
          onMute={() => onPatch({ music: { muted: !mix.music.muted } })}
          onSolo={() => onPatch({ music: { solo: !mix.music.solo } })}
        >{eq("music", sound)}</Strip>
        <Strip
          id="announcements" t={t} gain={mix.announcements.gain_db} muted={mix.announcements.muted} solo={mix.announcements.solo}
          silencedBySolo={solo && !mix.announcements.solo} level={level("announcements")}
          onGain={(db) => onPatch({ announcements: { gain_db: db } })}
          onMute={() => onPatch({ announcements: { muted: !mix.announcements.muted } })}
          onSolo={() => onPatch({ announcements: { solo: !mix.announcements.solo } })}
        >{eq("announcements", mix.announcements.sound)}</Strip>
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

export default function MixerSection({ refreshKey, notify, t, feed }: RadioSectionProps) {
  const stored = useDevicesResource<MixerView>("/mixer", refreshKey);
  // Réglage local pendant un glissement : l'état serveur n'arrive qu'après l'aller-retour, le curseur ne doit pas « sauter ».
  const [drafts, setDrafts] = useState<Partial<Record<RadioOutputId, { mix?: RadioMix; sound?: RadioSoundSettings }>>>({});
  const pending = useRef<Partial<Record<RadioOutputId, { mix?: MixPatch; sound?: RadioSoundSettings }>>>({});
  const timers = useRef<Partial<Record<RadioOutputId, ReturnType<typeof setTimeout>>>>({});

  const writes = useRef<Partial<Record<RadioOutputId, Promise<void>>>>({});
  const revision = useRef<Partial<Record<RadioOutputId, number>>>({});

  const flush = useCallback(async (channel: RadioOutputId) => {
    const body = pending.current[channel];
    pending.current[channel] = undefined;
    if (!body) return;
    const version = (revision.current[channel] ?? 0) + 1;
    revision.current[channel] = version;
    const write = (writes.current[channel] ?? Promise.resolve()).catch(() => {}).then(async () => {
      const result = await devicesRequest<MixerView>(`/mixer/${channel}`, { method: "PUT", body: { mix: body.mix, sound: body.sound } });
      if (revision.current[channel] === version && !pending.current[channel]) setDrafts((current) => ({ ...current, [channel]: undefined }));
      if (!result.ok) notify(errorText(result.error, t), "error");
    });
    writes.current[channel] = write;
    await write;
  }, [notify, t]);

  const flushRef = useRef(flush);
  useEffect(() => { flushRef.current = flush; }, [flush]);
  useEffect(() => () => {
    Object.values(timers.current).forEach((id) => id && clearTimeout(id));
    for (const channel of RADIO_OUTPUTS) void flushRef.current(channel);
  }, []);

  const schedule = useCallback((channel: RadioOutputId) => {
    const previous = timers.current[channel];
    if (previous) clearTimeout(previous);
    timers.current[channel] = setTimeout(() => void flush(channel), SEND_DELAY_MS);
  }, [flush]);

  const current = (channel: RadioOutputId): { mix: RadioMix; sound: RadioSoundSettings } => {
    const draft = drafts[channel];
    const live = feed.channels[channel];
    const saved = stored.data?.outputs.find((o) => o.channel === channel);
    return {
      mix: draft?.mix ?? live?.mix ?? (saved ? clampMix(saved.mix as Partial<RadioMix>) : defaultMix()),
      sound: draft?.sound ?? live?.sound ?? (saved ? clampSound(saved.sound as Partial<RadioSoundSettings>) : clampSound(null)),
    };
  };

  const patchMix = (channel: RadioOutputId, patch: MixPatch) => {
    const { mix } = current(channel);
    const next = clampMix(patch as Partial<RadioMix>, mix);
    setDrafts((d) => ({ ...d, [channel]: { ...d[channel], mix: next } }));
    const entry = pending.current[channel] ?? {};
    pending.current[channel] = { ...entry, mix: mergePatch(entry.mix ?? {}, patch) };
    schedule(channel);
  };

  const patchSound = (channel: RadioOutputId, sound: RadioSoundSettings, target: "music" | "announcements") => {
    if (target === "music") {
      setDrafts((d) => ({ ...d, [channel]: { ...d[channel], sound } }));
      pending.current[channel] = { ...pending.current[channel], sound };
      schedule(channel);
    } else {
      patchMix(channel, { announcements: { sound } });
    }
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
          const saved = stored.data?.outputs.find((o) => o.channel === channel);
          return (
            <ChannelMixer
              key={channel}
              channel={channel}
              mix={mix}
              sound={sound}
              playing={live?.playing ?? saved?.playing ?? false}
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
