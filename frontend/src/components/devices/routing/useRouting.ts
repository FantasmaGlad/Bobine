import { useMemo, useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { type RoutingView } from "@/lib/devices/routing";
import type { RadioChannelId } from "@/lib/outputs";
import { type AudioListing } from "@/lib/devices/types";
import { errorText, type SectionProps } from "../shared/section";
import { useDevicesResource } from "../shared/useDevicesResource";

export interface Assignment {
  channel: RadioChannelId;
  sinkId: string | null;
}

export function useRoutingModel(refreshKey: number) {
  const routing = useDevicesResource<RoutingView>("/routing", refreshKey);
  const audio = useDevicesResource<AudioListing>("/audio", refreshKey);
  const devices = useMemo(() => audio.data?.devices ?? [], [audio.data]);
  const outputs = useMemo(() => routing.data?.outputs ?? [], [routing.data]);
  return { routing, devices, outputs };
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
