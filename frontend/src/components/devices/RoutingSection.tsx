"use client";

import { useMemo, useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect, { type SelectOption } from "@/components/ResponsiveSelect";
import SegmentedTabs from "@/components/SegmentedTabs";
import {
  audioDisplayName, devicesRequest, summarizeRouting,
  type AudioListing, type RadioOutputId, type RoutingOutput, type RoutingView,
} from "@/lib/devicesApi";
import type { RadioFeed } from "@/lib/useRadioFeed";
import { buildRoutingGraph, type Assignment } from "@/lib/routingGraph";
import { errorText, useDevicesResource, type SectionProps } from "./common";
import RoutingGraph from "./RoutingGraph";

export type RadioSectionProps = SectionProps & { feed: RadioFeed };

const TONE_ICON = { neutral: "info", ok: "check_circle", info: "schedule", warn: "warning", bad: "error" } as const;

/** Demande au navigateur de révéler les noms de ses sorties audio (une permission micro de 0 s, flux aussitôt arrêté, rien n'est enregistré). */
async function unlockOutputLabels(): Promise<"ok" | "denied" | "unsupported"> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return "unsupported";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return "ok";
  } catch {
    return "denied";
  }
}

export default function RoutingSection({ caps, refreshKey, notify, t, feed }: RadioSectionProps) {
  const routing = useDevicesResource<RoutingView>("/routing", refreshKey);
  const audio = useDevicesResource<AudioListing>("/audio", refreshKey);
  const [busy, setBusy] = useState(false);

  const devices = useMemo(() => audio.data?.devices ?? [], [audio.data]);
  const outputs = useMemo(() => routing.data?.outputs ?? [], [routing.data]);
  const live = useMemo(() => {
    const map: Partial<Record<RadioOutputId, boolean>> = {};
    for (const [channel, value] of Object.entries(feed.channels)) if (value) map[channel as RadioOutputId] = value.playing;
    return map;
  }, [feed.channels]);
  const model = useMemo(
    () => buildRoutingGraph({ outputs, devices, playing: live, displayName: audioDisplayName, defaultLabel: t("devices.routing.defaultOutput") }),
    [outputs, devices, live, t],
  );

  const save = async (body: Record<string, unknown>, okMessage: string) => {
    setBusy(true);
    const result = await devicesRequest<RoutingView>("/routing", { method: "PUT", body });
    setBusy(false);
    if (result.ok) {
      notify(okMessage, "success");
      await routing.reload();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };
  const assign = ({ channel, sinkId }: Assignment) =>
    save(sinkId ? { channel, sink_id: sinkId } : { channel, clear: true }, sinkId ? t("devices.routing.saved") : t("devices.routing.cleared"));

  if (routing.loading || audio.loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (routing.error) return <div className="rl-center-note">{errorText(routing.error, t)}</div>;
  if (!routing.data?.supported) {
    return (
      <div className="rl-empty-state">
        <Icon name="alt_route" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.routing.unsupported")}</p>
        {routing.data?.reason && <p className="settings-hint">{routing.data.reason}</p>}
      </div>
    );
  }

  const sinkOptions: SelectOption[] = devices
    .filter((d) => d.available && !d.hidden)
    .map((d) => ({ value: d.id, label: audioDisplayName(d), sublabel: t(`devices.audio.kind.${d.kind}`) }));
  const summaries = outputs.map((o) => ({ output: o, summary: summarizeRouting(o) }));
  const needsLabels = summaries.some((s) => s.summary.key === "needsLabels");
  const serverUnavailable = !routing.data.server_mechanism?.supported;

  const unlock = async () => {
    const outcome = await unlockOutputLabels();
    notify(t(`devices.routing.unlock.${outcome}`), outcome === "ok" ? "success" : "warning");
  };

  const renderCard = ({ output, summary }: { output: RoutingOutput; summary: ReturnType<typeof summarizeRouting> }) => {
    const playing = live[output.channel] ?? output.playing;
    const route = output.route;
    const app = output.server?.app ?? "";
    return (
      <section key={output.channel} className="rt-card glass-interactive" data-focus-id={output.channel} aria-label={t(`devices.map.channels.${output.channel}`)}>
        <header className="rt-card-head">
          <span className="dv-icon"><Icon name="radio" size={22} /></span>
          <span className="dv-text">
            <span className="dv-title">
              {t(`devices.map.channels.${output.channel}`)}
              <span className={`dv-badge${playing ? "" : " dv-badge--muted"}`}>{playing ? t("devices.routing.playing") : t("devices.routing.stopped")}</span>
            </span>
            <span className="dv-sub">{feed.channels[output.channel]?.title ?? t("devices.routing.noTrack")}</span>
          </span>
        </header>
        <label className="rt-field">
          <span className="rt-field-label">{t("devices.routing.output")}</span>
          <ResponsiveSelect
            value={route?.sink_id ?? ""}
            placeholder={t("devices.routing.defaultOutput")}
            options={sinkOptions}
            disabled={busy}
            title={t("devices.routing.output")}
            onChange={(value) => void assign({ channel: output.channel, sinkId: value || null })}
          />
        </label>
        {route && (
          <div className="rt-field">
            <span className="rt-field-label">{t("devices.routing.fallback.label")}</span>
            <SegmentedTabs
              ariaLabel={t("devices.routing.fallback.label")}
              value={route.fallback}
              onChange={(id) => void save({ channel: output.channel, fallback: id }, t("devices.routing.saved"))}
              tabs={[
                { id: "default", icon: "volume_up", label: t("devices.routing.fallback.default") },
                { id: "mute", icon: "volume_off", label: t("devices.routing.fallback.mute") },
              ]}
            />
          </div>
        )}
        <p className={`rt-status rt-status--${summary.tone}`} role="status">
          <Icon name={TONE_ICON[summary.tone]} size={18} />
          <span>
            {t(`devices.routing.status.${summary.key}`, { name: route?.label ?? "", app })}
            {summary.extra && <span className="rt-status-extra"> {t(`devices.routing.status.${summary.extra}`)}</span>}
          </span>
        </p>
      </section>
    );
  };

  return (
    <div className="dv-section">
      <div className="dv-note">
        <Icon name="info" size={16} />
        <span>{t("devices.routing.intro")}</span>
      </div>
      <RoutingGraph model={model} t={t} disabled={busy || !caps.audio_list?.supported} onAssign={(a) => void assign(a)} />
      <div className="rt-cards">{summaries.map(renderCard)}</div>
      {needsLabels && (
        <div className="dv-note dv-note--strong">
          <Icon name="visibility" size={16} />
          <span>{t("devices.routing.unlock.hint")}</span>
          <button type="button" className="btn btn-secondary" onClick={() => void unlock()}>
            <Icon name="mic" size={14} /> {t("devices.routing.unlock.button")}
          </button>
        </div>
      )}
      {serverUnavailable && (
        <p className="settings-hint rt-mechanism">
          <Icon name="info" size={14} /> {routing.data.server_mechanism?.reason || t("devices.routing.noServerMechanism")}
        </p>
      )}
    </div>
  );
}
