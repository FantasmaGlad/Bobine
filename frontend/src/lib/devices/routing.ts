import type { AudioKind, CapabilityInfo } from "./types.ts";

export type RadioOutputId = "radio_cable" | "radio_network";

export const RADIO_OUTPUTS: RadioOutputId[] = ["radio_cable", "radio_network"];

export interface RoutingRoute {
  sink_id: string;
  key: string;
  label: string;
  kind: AudioKind;
  fallback: "default" | "mute";
}

export interface RoutingPlayer {
  local: boolean;
  primary: boolean;
  status: string | null;
}

export interface RoutingServerStatus {
  status: "browser" | "waiting" | "moved" | "unchanged" | "released" | "no_stream" | "ambiguous" | "failed" | "unsupported";
  app?: string;
  detail?: string;
  reason?: string;
}

export interface RoutingOutput {
  channel: RadioOutputId;
  route: RoutingRoute | null;
  state: "default" | "routed" | "missing" | "unknown";
  sink_id: string | null;
  playing: boolean;
  players: RoutingPlayer[];
  server: RoutingServerStatus | null;
}

export interface RoutingView {
  supported: boolean;
  reason: string | null;
  server_mechanism: CapabilityInfo;
  fallbacks: Array<"default" | "mute">;
  outputs: RoutingOutput[];
}

export type RoutingTone = "neutral" | "ok" | "info" | "warn" | "bad";

export interface RoutingSummary {
  tone: RoutingTone;
  key: string;
  extra?: string;
}

const PLAYER_PROBLEMS: Record<string, string> = {
  unsupported: "unsupported",
  insecure: "insecure",
  needs_labels: "needsLabels",
  no_match: "noMatch",
  error: "error",
};

export function summarizeRouting(output: Pick<RoutingOutput, "route" | "state" | "players" | "server">): RoutingSummary {
  const { route, state, players, server } = output;
  if (!route) return { tone: "neutral", key: "none" };
  if (state === "missing") return { tone: "warn", key: route.fallback === "mute" ? "missingMuted" : "missingDefault" };
  if (players.some((p) => p.status === "applied")) return { tone: "ok", key: "appliedBrowser" };
  if (server && (server.status === "moved" || server.status === "unchanged")) return { tone: "ok", key: "appliedServer" };
  if (players.length === 0) return { tone: "info", key: "noPlayer" };
  const ordered = [...players].sort((a, b) => Number(b.local) - Number(a.local) || Number(b.primary) - Number(a.primary));
  const problem = ordered.map((p) => (p.status ? PLAYER_PROBLEMS[p.status] : undefined)).find(Boolean);
  const extra = server && ["ambiguous", "failed", "no_stream"].includes(server.status)
    ? (server.status === "no_stream" ? "serverNoStream" : server.status === "ambiguous" ? "serverAmbiguous" : "serverFailed")
    : undefined;
  if (problem) return { tone: problem === "error" ? "bad" : "warn", key: problem, extra };
  return { tone: "info", key: "pending", extra };
}

export function outputLabelsHidden(devices: Array<{ kind: string; label: string }>): boolean {
  const outputs = devices.filter((d) => d.kind === "audiooutput");
  return outputs.length > 0 && outputs.every((d) => !d.label);
}

export interface MixerOutput {
  channel: RadioOutputId;
  mix: unknown;
  sound: unknown;
  playing: boolean;
}

export interface MixerView {
  outputs: MixerOutput[];
}
