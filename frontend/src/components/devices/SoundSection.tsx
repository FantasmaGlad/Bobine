"use client";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import type { SelectOption } from "@/components/select/options";
import { audioDisplayName } from "@/lib/devices/audio";
import { RADIO_OUTPUTS, summarizeRouting, type RadioOutputId, type RoutingRoute } from "@/lib/devices/routing";
import { hasSolo } from "@/lib/radioMix";
import type { RadioFeed } from "@/lib/useRadioFeed";
import { useRadioMixer } from "./mixer/useRadioMixer";
import { UnlockLabelsNote } from "./routing/RoutingNotes";
import { useRoutingModel, useRoutingSave, type RoutingSave } from "./routing/useRouting";
import { errorText, type SectionProps } from "./shared/section";
import SoundRow from "./sound/SoundRow";
import { useVideoSound, VIDEO_CHANNELS } from "./sound/useVideoSound";

type Props = SectionProps & { feed: RadioFeed };

function OutputCell({ channel, route, options, saver, disabled, t }: {
  channel: RadioOutputId; route: RoutingRoute | null; options: SelectOption[]; saver: RoutingSave; disabled: boolean; t: SectionProps["t"];
}) {
  return (
    <div className="sd-output-cell">
      <ResponsiveSelect value={route?.sink_id ?? ""} placeholder={t("devices.routing.defaultOutput")} options={options} disabled={disabled}
        title={t("devices.routing.output")} onChange={(value) => void saver.assign({ channel, sinkId: value || null })} />
      {route && (
        <label className="sd-fallback">
          <input type="checkbox" checked={route.fallback === "mute"} disabled={disabled}
            onChange={(e) => void saver.save({ channel, fallback: e.target.checked ? "mute" : "default" }, t("devices.routing.saved"))} />
          {t("devices.routing.muteWhenUnplugged")}
        </label>
      )}
    </div>
  );
}

const WARNING_TONES = new Set(["warn", "bad"]);

export default function SoundSection({ caps, refreshKey, notify, t, feed }: Props) {
  const { routing, devices, outputs } = useRoutingModel(refreshKey);
  const saver = useRoutingSave(notify, t, routing.reload);
  const mixer = useRadioMixer(refreshKey, feed, notify, t);
  const video = useVideoSound(refreshKey, notify, t);

  if (mixer.stored.error) return <div className="rl-center-note">{errorText(mixer.stored.error, t)}</div>;

  const routable = !!routing.data?.supported;
  const options: SelectOption[] = devices.filter((d) => d.available && !d.hidden)
    .map((d) => ({ value: d.id, label: audioDisplayName(d), sublabel: t(`devices.audio.kind.${d.kind}`) }));
  const needsLabels = outputs.some((o) => summarizeRouting(o).key === "needsLabels");

  return (
    <div className="dv-section sd-table" role="table" aria-label={t("devices.tabs.sound")}>
      {RADIO_OUTPUTS.map((channel) => {
        const { mix, sound, playing } = mixer.current(channel);
        const levels = playing ? feed.levels[channel] : undefined;
        const output = outputs.find((o) => o.channel === channel);
        const route = output?.route ?? null;
        const summary = output ? summarizeRouting(output) : null;
        const name = t(`devices.channels.${channel}`);
        return (
          <section key={channel} className="sd-group" aria-label={name}>
            {hasSolo(mix) && (
              <p className="dv-note">
                <Icon name="info" size={16} /><span>{t("devices.mixer.soloActive")}</span>
                <button type="button" className="btn btn-secondary" onClick={() => mixer.patchMix(channel, { music: { solo: false }, announcements: { solo: false } })}>
                  {t("devices.mixer.soloClear")}
                </button>
              </p>
            )}
            <SoundRow icon="radio" title={name} t={t}
              sub={playing ? feed.channels[channel]?.title ?? t("devices.routing.playing") : t("devices.routing.stopped")}
              output={routable
                ? <OutputCell channel={channel} route={route} options={options} saver={saver} disabled={saver.busy || !caps.audio_list?.supported} t={t} />
                : <span className="dv-sub">{t("devices.routing.defaultOutput")}</span>}
              fader={{ gain: mix.master.gain_db, muted: mix.master.muted, level: levels?.master,
                onGain: (db) => mixer.patchMix(channel, { master: { gain_db: db } }),
                onMute: () => mixer.patchMix(channel, { master: { muted: !mix.master.muted } }) }}
              sound={sound} onSound={(next) => mixer.patchSound(channel, next)} />
            {summary && WARNING_TONES.has(summary.tone) && (
              <p className="dv-note dv-note--strong" role="status">
                <Icon name="warning" size={16} />
                <span>{t(`devices.routing.status.${summary.key}`, { name: route?.label ?? "", app: output?.server?.app ?? "" })}</span>
              </p>
            )}
            <SoundRow icon="campaign" title={t("devices.mixer.strips.announcements")} nested t={t}
              fader={{ gain: mix.announcements.gain_db, muted: mix.announcements.muted, level: levels?.announcements,
                onGain: (db) => mixer.patchMix(channel, { announcements: { gain_db: db } }),
                onMute: () => mixer.patchMix(channel, { announcements: { muted: !mix.announcements.muted } }) }}
              sound={mix.announcements.sound} onSound={(next) => mixer.patchMix(channel, { announcements: { sound: next } })} />
          </section>
        );
      })}
      <section className="sd-group" aria-label={t("devices.videoSound.title")}>
        {VIDEO_CHANNELS.map((channel) => (
          <SoundRow key={channel} icon="movie" title={t(`devices.sound.video.${channel}`)} t={t}
            sound={video.sounds[channel]} onSound={(next) => video.save(channel, next)} />
        ))}
      </section>
      {needsLabels && <UnlockLabelsNote notify={notify} t={t} />}
    </div>
  );
}
