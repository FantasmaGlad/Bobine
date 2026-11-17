import type { AudioDevice, AudioKind } from "./types.ts";

export function audioKindIcon(kind: AudioKind): string {
  switch (kind) {
    case "hdmi": return "settings_input_hdmi";
    case "usb": return "usb";
    case "jack": return "headphones";
    case "bluetooth": return "bluetooth_audio";
    case "virtual": return "memory";
    case "internal": return "speaker";
    default: return "volume_up";
  }
}

export function audioDisplayName(device: Pick<AudioDevice, "name" | "alias">): string {
  return device.alias?.trim() || device.name;
}

export function balanceFromSlider(value: number): number {
  const clamped = Math.max(-100, Math.min(100, value));
  return Math.abs(clamped) <= 4 ? 0 : Math.round(clamped) / 100;
}

export function sliderFromBalance(balance: number): number {
  return Math.round(Math.max(-1, Math.min(1, balance)) * 100);
}

export type BalanceSide = "left" | "right" | "center";

export function describeBalance(balance: number): { side: BalanceSide; percent: number } {
  if (Math.abs(balance) < 0.005) return { side: "center", percent: 100 };
  return balance < 0
    ? { side: "left", percent: Math.round((1 - -balance) * 100) }
    : { side: "right", percent: Math.round((1 - balance) * 100) };
}

export function formatSampleRate(rate: number | null | undefined): string {
  if (!rate) return "—";
  return rate % 1000 === 0 ? `${rate / 1000} kHz` : `${(rate / 1000).toFixed(1)} kHz`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return ms >= 100 ? `${Math.round(ms)} ms` : `${ms.toFixed(1)} ms`;
}

export function describeChannels(count: number | null | undefined, map: string[], t?: (key: string, params?: Record<string, string | number>) => string): string {
  const tr = t ?? ((key: string, params?: Record<string, string | number>) => ({
    "devices.channelWords.mono": "Mono", "devices.channelWords.stereo": "Stéréo", "devices.channelWords.stereoMap": `Stéréo (${params?.map})`,
    "devices.channelWords.count": `${params?.count} canaux`, "devices.channelWords.left": "G", "devices.channelWords.right": "D", "devices.channelWords.rearLeft": "AG", "devices.channelWords.rearRight": "AD", "devices.channelWords.sideLeft": "G latéral", "devices.channelWords.sideRight": "D latéral",
  }[key] ?? key));
  if (!count) return "—";
  const short: Record<string, string> = { FL: tr("devices.channelWords.left"), FR: tr("devices.channelWords.right"), FC: "C", LFE: "LFE", RL: tr("devices.channelWords.rearLeft"), RR: tr("devices.channelWords.rearRight"), SL: tr("devices.channelWords.sideLeft"), SR: tr("devices.channelWords.sideRight"), MONO: "M" };
  const labels = map.map((c) => short[c] ?? c);
  if (count === 1) return tr("devices.channelWords.mono");
  if (count === 2) return labels.length ? tr("devices.channelWords.stereoMap", { map: labels.join(", ") }) : tr("devices.channelWords.stereo");
  return tr("devices.channelWords.count", { count });
}
