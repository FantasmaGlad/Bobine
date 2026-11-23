import {
  DEFAULT_OUTPUT,
  DEFAULT_RADIO_CHANNEL,
  DISPLAY_MODES,
  NETWORK_FALLBACK,
  WIRED_OUTPUT,
  hasMode,
  isOutputId,
  outputById,
  outputOfRadio,
  type DisplayMode,
  type OutputId,
  type RadioChannelId,
} from "./outputs.ts";

export type DisplayChannel = OutputId;

export type ChannelSource = "query" | "default";

export type DisplayOutput = DisplayMode;

export type DisplayPage = DisplayOutput;

export type LockedOutput = Exclude<DisplayOutput, "kiosk">;

export function outputsFor(channel: DisplayChannel): readonly DisplayOutput[] {
  return outputById(channel).modes;
}

export function parseDisplayOutput(channel: DisplayChannel, value: unknown): DisplayOutput | null {
  return outputsFor(channel).find((output) => output === value) ?? null;
}

export function lockedOutput(reason: unknown): LockedOutput | null {
  const output = typeof reason === "string" && reason.endsWith("_locked") ? reason.slice(0, -"_locked".length) : null;
  return DISPLAY_MODES.find((candidate): candidate is LockedOutput => candidate !== "kiosk" && candidate === output) ?? null;
}

export interface ResolvedChannel {
  channel: DisplayChannel;
  source: ChannelSource;
}

export function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "[::1]" || hostname === "::1";
}

export function parseChannelParam(search: string): DisplayChannel | null {
  const value = new URLSearchParams(search).get("channel");
  return isOutputId(value) ? value : null;
}

export function resolveChannel(search: string, hostname: string, page: DisplayPage): ResolvedChannel {
  const explicit = parseChannelParam(search);
  if (explicit) return { channel: explicit, source: "query" };
  if (page === "kiosk") return { channel: DEFAULT_OUTPUT, source: "default" };
  if (page === "radio") return { channel: outputOfRadio(DEFAULT_RADIO_CHANNEL).id, source: "default" };
  return { channel: isLoopbackHost(hostname) ? WIRED_OUTPUT : NETWORK_FALLBACK, source: "default" };
}

export function buildOutputUrl(target: DisplayPage, search: string, channel: DisplayChannel): string {
  const params = new URLSearchParams(search);
  params.set("channel", channel);
  return `/${target}?${params.toString()}`;
}

export function screenUrl(channel: DisplayChannel, output: DisplayOutput | null): string {
  return buildOutputUrl(output ?? "kiosk", "", channel);
}

export function shouldFollowInitialOutput(channel: DisplayChannel, page: DisplayPage = "kiosk"): boolean {
  if (page === "radio") return false;
  return outputById(channel).wired;
}

export function radioChannelId(channel: DisplayChannel): RadioChannelId {
  return outputById(channel).radioChannel;
}

export interface OutputRedirectDecision {
  seen: DisplayOutput | null;
  to: string | null;
}

export function decideOutputRedirect(
  current: DisplayPage,
  search: string,
  hostname: string,
  cableOutput: DisplayOutput | null,
  networkOutput: DisplayOutput | null,
  previous: DisplayOutput | null,
): OutputRedirectDecision {
  const { channel } = resolveChannel(search, hostname, current);
  const target = channel === "cable" ? cableOutput : networkOutput;
  if (!target) return { seen: previous, to: null };

  const seen = target;
  if (target === "radio" && !hasMode(channel, "radio")) return { seen, to: null };
  if (current === "radio" && !hasMode(channel, "radio")) return { seen, to: null };
  if (target === current) return { seen, to: null };
  if (current === "radio" && previous !== "radio") return { seen, to: null };
  if (!shouldFollowInitialOutput(channel, current) && previous === null) return { seen, to: null };
  return { seen, to: buildOutputUrl(target, search, channel) };
}

export function shouldEvaluateRedirect(
  channel: DisplayChannel,
  cableOutput: DisplayOutput | null,
  networkOutput: DisplayOutput | null,
  lastSeen: DisplayOutput | null,
): boolean {
  const target = channel === "cable" ? cableOutput : networkOutput;
  if (!target) return false;
  return lastSeen === null || target !== lastSeen;
}

export function createPageClientId(random: () => string = defaultRandomId): string {
  return `kiosk-${random()}`;
}

function defaultRandomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
