export const OUTPUTS = [
  { id: "cable", radioChannel: "radio_cable", modes: ["kiosk", "cinema", "radio", "signage"], wired: true, coach: true },
  { id: "network", radioChannel: "radio_network", modes: ["kiosk", "cinema", "signage"], wired: false, coach: false },
] as const;

export type OutputSpec = (typeof OUTPUTS)[number];
export type OutputId = OutputSpec["id"];
export type RadioChannelId = OutputSpec["radioChannel"];
export type DisplayMode = OutputSpec["modes"][number];

export const OUTPUT_IDS: readonly OutputId[] = OUTPUTS.map((output) => output.id);
export const RADIO_CHANNELS: readonly RadioChannelId[] = OUTPUTS.map((output) => output.radioChannel);
export const DISPLAY_MODES: readonly DisplayMode[] = [...new Set(OUTPUTS.flatMap((output): readonly DisplayMode[] => output.modes))];

export function outputById(id: OutputId): OutputSpec {
  return OUTPUTS.find((output) => output.id === id) ?? OUTPUTS[0];
}

export function isOutputId(value: unknown): value is OutputId {
  return OUTPUT_IDS.some((id) => id === value);
}

export function isRadioChannel(value: unknown): value is RadioChannelId {
  return RADIO_CHANNELS.some((channel) => channel === value);
}

export function outputOfRadio(channel: RadioChannelId): OutputSpec {
  return OUTPUTS.find((output) => output.radioChannel === channel) ?? OUTPUTS[0];
}

export function hasMode(id: OutputId, mode: DisplayMode): boolean {
  return outputById(id).modes.some((candidate) => candidate === mode);
}

export const DEFAULT_OUTPUT: OutputId = OUTPUTS[0].id;
export const WIRED_OUTPUT: OutputId = (OUTPUTS.find((output) => output.wired) ?? OUTPUTS[0]).id;
export const DEFAULT_RADIO_CHANNEL: RadioChannelId = outputById("network").radioChannel;
export const NETWORK_FALLBACK: OutputId = (OUTPUTS.find((output) => !output.wired) ?? OUTPUTS[0]).id;
