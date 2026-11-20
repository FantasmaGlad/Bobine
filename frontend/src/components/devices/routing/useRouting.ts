import { useMemo, useState } from "react";
import { audioDisplayName } from "@/lib/devices/audio";
import { devicesRequest } from "@/lib/devices/request";
import { type RadioOutputId, type RoutingView } from "@/lib/devices/routing";
import { type AudioListing } from "@/lib/devices/types";
import type { RadioFeed } from "@/lib/useRadioFeed";
import { buildRoutingGraph, type Assignment } from "@/lib/routingGraph";
import { errorText, type SectionProps } from "../shared/section";
import { useDevicesResource } from "../shared/useDevicesResource";

export function useRoutingModel(refreshKey: number, feed: RadioFeed, t: SectionProps["t"]) {
  const routing = useDevicesResource<RoutingView>("/routing", refreshKey);
  const audio = useDevicesResource<AudioListing>("/audio", refreshKey);
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
  return { routing, audio, devices, outputs, live, model };
}

export function useRoutingSave(notify: SectionProps["notify"], t: SectionProps["t"], reload: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const save = async (body: Record<string, unknown>, okMessage: string) => {
    setBusy(true);
    const result = await devicesRequest<RoutingView>("/routing", { method: "PUT", body });
    setBusy(false);
    if (result.ok) {
      notify(okMessage, "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };
  const assign = ({ channel, sinkId }: Assignment) =>
    save(sinkId ? { channel, sink_id: sinkId } : { channel, clear: true }, sinkId ? t("devices.routing.saved") : t("devices.routing.cleared"));
  return { busy, save, assign };
}

export type RoutingSave = ReturnType<typeof useRoutingSave>;
