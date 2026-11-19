"use client";

import Icon from "@/components/Icon";
import type { SelectOption } from "@/components/select/options";
import { audioDisplayName } from "@/lib/devices/audio";
import { summarizeRouting } from "@/lib/devices/routing";
import type { RadioFeed } from "@/lib/useRadioFeed";
import { errorText, type SectionProps } from "./common";
import RoutingCard from "./routing/RoutingCard";
import { RoutingUnsupported, UnlockLabelsNote } from "./routing/RoutingNotes";
import { useRoutingModel, useRoutingSave } from "./routing/useRouting";
import RoutingGraph from "./RoutingGraph";

export type RadioSectionProps = SectionProps & { feed: RadioFeed };

export default function RoutingSection({ caps, refreshKey, notify, t, feed }: RadioSectionProps) {
  const { routing, audio, devices, outputs, live, model } = useRoutingModel(refreshKey, feed, t);
  const saver = useRoutingSave(notify, t, routing.reload);

  if (routing.loading || audio.loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (routing.error) return <div className="rl-center-note">{errorText(routing.error, t)}</div>;
  if (!routing.data?.supported) return <RoutingUnsupported reason={routing.data?.reason} t={t} />;

  const sinkOptions: SelectOption[] = devices
    .filter((d) => d.available && !d.hidden)
    .map((d) => ({ value: d.id, label: audioDisplayName(d), sublabel: t(`devices.audio.kind.${d.kind}`) }));
  const summaries = outputs.map((o) => ({ output: o, summary: summarizeRouting(o) }));
  const needsLabels = summaries.some((s) => s.summary.key === "needsLabels");
  const serverUnavailable = !routing.data.server_mechanism?.supported;

  return (
    <div className="dv-section">
      <div className="dv-note">
        <Icon name="info" size={16} />
        <span>{t("devices.routing.intro")}</span>
      </div>
      <RoutingGraph model={model} t={t} disabled={saver.busy || !caps.audio_list?.supported} onAssign={(a) => void saver.assign(a)} />
      <div className="rt-cards">
        {summaries.map(({ output, summary }) => (
          <RoutingCard key={output.channel} output={output} summary={summary} playing={live[output.channel] ?? output.playing} feed={feed} sinkOptions={sinkOptions} saver={saver} t={t} />
        ))}
      </div>
      {needsLabels && <UnlockLabelsNote notify={notify} t={t} />}
      {serverUnavailable && (
        <p className="settings-hint rt-mechanism">
          <Icon name="info" size={14} /> {routing.data.server_mechanism?.reason || t("devices.routing.noServerMechanism")}
        </p>
      )}
    </div>
  );
}
