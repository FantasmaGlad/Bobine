export type ScheduleChannel = "cable" | "network" | "radio_cable" | "radio_network";

export const SCHEDULE_CHANNELS: ScheduleChannel[] = ["cable", "network", "radio_cable", "radio_network"];

export function isRadioLane(channel: ScheduleChannel): boolean {
  return channel === "radio_cable" || channel === "radio_network";
}

export function parseScheduleChannel(requested: string | null | undefined): ScheduleChannel {
  if (requested === "radio") return "radio_network";
  return SCHEDULE_CHANNELS.includes(requested as ScheduleChannel) ? (requested as ScheduleChannel) : "cable";
}
