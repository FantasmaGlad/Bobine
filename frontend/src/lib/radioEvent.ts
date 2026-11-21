import type { RadioState } from "@/lib/useRadioSocket";

export type RadioStatePatch = Omit<RadioState, "order"> & { order?: RadioState["order"] };

export const SILENT_LINK_MS = 75_000;

export function mergeRadioState(previous: RadioState, data: RadioStatePatch): RadioState {
  return data.order === undefined ? { ...data, order: previous.order } : (data as RadioState);
}
