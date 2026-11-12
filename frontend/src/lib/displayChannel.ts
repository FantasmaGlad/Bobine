export type DisplayChannel = "cable" | "network";

export type ChannelSource = "query" | "default";

export type DisplayPage = "kiosk" | "cinema" | "radio";

export type DisplayOutput = "kiosk" | "cinema" | "radio";

export type RadioChannelId = "radio_cable" | "radio_network";

export interface ResolvedChannel {
  channel: DisplayChannel;
  source: ChannelSource;
}

export function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "[::1]" || hostname === "::1";
}

export function parseChannelParam(search: string): DisplayChannel | null {
  const value = new URLSearchParams(search).get("channel");
  return value === "cable" || value === "network" ? value : null;
}

export function resolveChannel(search: string, hostname: string, page: DisplayPage): ResolvedChannel {
  const explicit = parseChannelParam(search);
  if (explicit) return { channel: explicit, source: "query" };
  if (page === "kiosk") return { channel: "cable", source: "default" };
  if (page === "radio") return { channel: "network", source: "default" };
  return { channel: isLoopbackHost(hostname) ? "cable" : "network", source: "default" };
}

export function buildOutputUrl(target: DisplayPage, search: string, channel: DisplayChannel): string {
  const params = new URLSearchParams(search);
  params.set("channel", channel);
  return `/${target}?${params.toString()}`;
}

export function shouldFollowInitialOutput(channel: DisplayChannel, page: DisplayPage = "kiosk"): boolean {
  if (page === "radio") return false;
  return channel === "cable";
}

export function radioChannelId(channel: DisplayChannel): RadioChannelId {
  return channel === "cable" ? "radio_cable" : "radio_network";
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
  if (target === "radio" && channel !== "cable") return { seen, to: null };
  if (current === "radio" && channel !== "cable") return { seen, to: null };
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
