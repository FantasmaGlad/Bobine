export const ENTRY_STEP_MS = 20;
export const MAX_ENTRY_DELAY_MS = 80;

export function entryDelayMs(index: number): number {
  return Math.min(Math.max(0, index) * ENTRY_STEP_MS, MAX_ENTRY_DELAY_MS);
}
