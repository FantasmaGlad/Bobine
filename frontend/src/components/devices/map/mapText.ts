import { type PlacedNode, type Topology } from "@/lib/deviceMap";
import { type SectionProps } from "../common";

type T = SectionProps["t"];

export const truncate = (text: string, max = 18) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

export function nodeLabel(n: PlacedNode, t: T): string {
  if (n.kind !== "screen" && n.kind !== "remote") return n.label;
  const page = String(n.meta.page ?? "viewer");
  const key = `devices.map.pages.${page}`;
  const name = t(key) === key ? page : t(key);
  const count = Number(n.meta.count ?? 1);
  return count > 1 ? `${name} ×${count}` : name;
}

type Push = (key: string, value: unknown) => void;

function pushNetwork(node: PlacedNode, push: Push, t: T) {
  const m = node.meta;
  if (node.kind === "wifi") {
    push("network", node.label); push("signal", m.signal !== undefined ? `${m.signal} %` : null); push("band", m.band); push("security", m.security || t("devices.wifi.open")); push("ip", m.ip);
  } else {
    push("interface", m.interface); push("ip", m.ip); push("speed", m.speed ? `${m.speed} Mb/s` : null);
  }
}

function pushBluetooth(node: PlacedNode, push: Push, t: T) {
  const m = node.meta;
  push("address", m.address); push("state", m.connected ? t("devices.bluetooth.connected") : t("devices.map.paired"));
  push("profiles", Array.isArray(m.profiles) ? (m.profiles as string[]).join(", ") : null); push("battery", m.battery !== null && m.battery !== undefined ? `${m.battery} %` : null);
  push("audioOutput", m.audio_id ? t(m.audio_default ? "devices.map.audioDefault" : "devices.map.audioAvailable") : null);
}

function pushScreen(node: PlacedNode, label: string, push: Push, t: T) {
  const m = node.meta;
  push("page", label); push("channel", t(`devices.map.channels.${m.channel}`)); push("role", t(`devices.map.roles.${m.role}`));
  push("address", m.ip || t("devices.map.localScreen")); push("link", t(`devices.map.medium.${m.medium}`)); push("count", Number(m.count ?? 1) > 1 ? m.count : null);
}

export function panelRows(node: PlacedNode, label: string, topology: Topology, t: T): [string, string][] {
  const m = node.meta;
  const rows: [string, string][] = [];
  const push: Push = (key, value) => { if (value !== null && value !== undefined && value !== "") rows.push([t(`devices.map.fields.${key}`), String(value)]); };
  switch (node.kind) {
    case "machine":
      push("platform", node.sub);
      push("audio", topology.counts.audio);
      push("bluetooth", topology.counts.bluetooth);
      push("screens", topology.counts.screens);
      break;
    case "wifi":
    case "ethernet":
      pushNetwork(node, push, t);
      break;
    case "bluetooth":
      pushBluetooth(node, push, t);
      break;
    case "audio":
      push("type", t(`devices.audio.kind.${m.device_kind}`)); push("state", m.default ? t("devices.audio.default") : t("devices.map.idle"));
      push("volume", typeof m.volume === "number" ? `${Math.round(m.volume * 100)} %` : null);
      break;
    default:
      pushScreen(node, label, push, t);
  }
  return rows;
}
