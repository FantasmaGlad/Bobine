import { DEFAULT_OUTPUT, OUTPUT_IDS, isOutputId, type OutputId } from "./outputs.ts";

export type ScheduleChannel = OutputId;

export const SCHEDULE_CHANNELS: readonly ScheduleChannel[] = OUTPUT_IDS;

export function parseScheduleChannel(requested: string | null | undefined): ScheduleChannel {
  return isOutputId(requested) ? requested : DEFAULT_OUTPUT;
}
