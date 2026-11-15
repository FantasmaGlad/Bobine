export const STALL_TIMEOUT_MS = 15000;
export const STALL_CHECK_MS = 5000;
export const RECOVERY_GRACE_MS = 10000;
export const RECOVERY_POLL_MS = 1000;

export type RecoveryOutcome = "recovered" | "wait" | "skip" | "give_up";

export function stalled(playing: boolean, announcing: boolean, recovering: boolean, sinceProgressMs: number) {
  if (!playing || announcing || recovering) return false;
  return sinceProgressMs > STALL_TIMEOUT_MS;
}

export function recoveryOutcome(
  progressedSinceAttempt: boolean,
  elapsedMs: number,
  stillActive: boolean,
  playing: boolean,
  announcing: boolean,
): RecoveryOutcome {
  if (progressedSinceAttempt) return "recovered";
  if (elapsedMs < RECOVERY_GRACE_MS) return "wait";
  return stillActive && playing && !announcing ? "skip" : "give_up";
}
