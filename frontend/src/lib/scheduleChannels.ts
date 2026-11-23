import { DEFAULT_OUTPUT, DEFAULT_RADIO_CHANNEL, OUTPUT_IDS, isOutputId, isRadioChannel, outputOfRadio, type OutputId } from "./outputs.ts";

export type ScheduleChannel = OutputId;

export const SCHEDULE_CHANNELS: readonly ScheduleChannel[] = OUTPUT_IDS;

export function parseScheduleChannel(requested: string | null | undefined): ScheduleChannel {
  if (isOutputId(requested)) return requested;
  if (requested === "radio") return outputOfRadio(DEFAULT_RADIO_CHANNEL).id;
  if (isRadioChannel(requested)) return outputOfRadio(requested).id;
  return DEFAULT_OUTPUT;
}
