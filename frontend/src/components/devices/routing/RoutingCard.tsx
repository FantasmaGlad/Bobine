"use client";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import type { SelectOption } from "@/components/select/options";
import SegmentedTabs from "@/components/SegmentedTabs";
import { type summarizeRouting, type RoutingOutput } from "@/lib/devices/routing";
import type { RadioFeed } from "@/lib/useRadioFeed";
import { type SectionProps } from "../shared/section";
import { type RoutingSave } from "./useRouting";

const TONE_ICON = { neutral: "info", ok: "check_circle", info: "schedule", warn: "warning", bad: "error" } as const;

interface CardProps {
  output: RoutingOutput;
  summary: ReturnType<typeof summarizeRouting>;
  playing: boolean;
  feed: RadioFeed;
  sinkOptions: SelectOption[];
  saver: RoutingSave;
  t: SectionProps["t"];
}

function CardHead({ output, playing, feed, t }: CardProps) {
  return (
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
  );
}

function FallbackField({ output, saver, t }: CardProps) {
  return (
    <div className="rt-field">
      <span className="rt-field-label">{t("devices.routing.fallback.label")}</span>
      <SegmentedTabs
        ariaLabel={t("devices.routing.fallback.label")}
        value={output.route!.fallback}
        onChange={(id) => void saver.save({ channel: output.channel, fallback: id }, t("devices.routing.saved"))}
        tabs={[
          { id: "default", icon: "volume_up", label: t("devices.routing.fallback.default") },
          { id: "mute", icon: "volume_off", label: t("devices.routing.fallback.mute") },
        ]}
      />
    </div>
  );
}

export default function RoutingCard(props: CardProps) {
  const { output, summary, sinkOptions, saver, t } = props;
  const route = output.route;
  const app = output.server?.app ?? "";
  return (
    <section className="rt-card glass-interactive" data-focus-id={output.channel} aria-label={t(`devices.map.channels.${output.channel}`)}>
      <CardHead {...props} />
      <label className="rt-field">
        <span className="rt-field-label">{t("devices.routing.output")}</span>
        <ResponsiveSelect
          value={route?.sink_id ?? ""}
          placeholder={t("devices.routing.defaultOutput")}
          options={sinkOptions}
          disabled={saver.busy}
          title={t("devices.routing.output")}
          onChange={(value) => void saver.assign({ channel: output.channel, sinkId: value || null })}
        />
      </label>
      {route && <FallbackField {...props} />}
      <p className={`rt-status rt-status--${summary.tone}`} role="status">
        <Icon name={TONE_ICON[summary.tone]} size={18} />
        <span>
          {t(`devices.routing.status.${summary.key}`, { name: route?.label ?? "", app })}
          {summary.extra && <span className="rt-status-extra"> {t(`devices.routing.status.${summary.extra}`)}</span>}
        </span>
      </p>
    </section>
  );
}
