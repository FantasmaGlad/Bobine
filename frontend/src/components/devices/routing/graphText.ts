import { audioKindIcon } from "@/lib/devices/audio";
import { type GraphSink, type GraphSource } from "@/lib/routingGraph";
import { type SectionProps } from "../shared/section";

type T = SectionProps["t"];

export function sourceIcon(source: GraphSource): string {
  if (source.kind === "radio") return "radio";
  return source.kind === "announcements" ? "campaign" : "movie";
}

export function sinkIcon(sink: GraphSink): string {
  return sink.kind === "default" ? "volume_up" : audioKindIcon(sink.kind);
}

export function sourceLabel(s: GraphSource, t: T): string {
  return s.channel ? t(`devices.map.channels.${s.channel}`) : t(`devices.routing.graph.${s.kind}`);
}

export function sourceSub(s: GraphSource, t: T): string {
  if (s.kind === "radio") return s.playing ? t("devices.routing.playing") : t("devices.routing.stopped");
  return s.kind === "announcements" ? t("devices.routing.graph.announcementsSub") : t("devices.routing.graph.videoSub");
}

export function sinkSub(s: GraphSink, t: T): string {
  if (s.absent) return t("devices.routing.graph.absent");
  if (s.kind === "default") return t("devices.routing.graph.defaultSub");
  return `${t(`devices.audio.kind.${s.kind}`)}${s.isDefault ? ` · ${t("devices.audio.default")}` : ""}`;
}
