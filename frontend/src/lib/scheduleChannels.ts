import { DEFAULT_OUTPUT, DEFAULT_RADIO_CHANNEL, OUTPUT_IDS, RADIO_CHANNELS, isRadioChannel, type OutputId, type RadioChannelId } from "./outputs.ts";

export type ScheduleChannel = OutputId | RadioChannelId;

export const SCHEDULE_CHANNELS: readonly ScheduleChannel[] = [...OUTPUT_IDS, ...RADIO_CHANNELS];

export function isRadioLane(channel: ScheduleChannel): boolean {
  return isRadioChannel(channel);
}

export function parseScheduleChannel(requested: string | null | undefined): ScheduleChannel {
  if (requested === "radio") return DEFAULT_RADIO_CHANNEL;
  return SCHEDULE_CHANNELS.includes(requested as ScheduleChannel) ? (requested as ScheduleChannel) : DEFAULT_OUTPUT;
}
