export const SCRUB_COMMIT_DELAY_MS = 350;
export const SCRUB_STEP_INTERVAL_MS = 110;

export function scrubStep(heldMs: number): number {
  if (heldMs < 800) return 10;
  if (heldMs < 2000) return 30;
  if (heldMs < 4000) return 60;
  return 120;
}

export interface ScrubClock {
  now: () => number;
  setTimer: (callback: () => void, delayMs: number) => unknown;
  clearTimer: (timer: unknown) => void;
}

export interface ScrubTarget {
  onPreview: (seconds: number) => void;
  onCommit: (seconds: number) => void;
}

interface Session {
  direction: 1 | -1;
  startedAt: number;
  lastStepAt: number;
  target: number;
}

export class Scrubber {
  private session: Session | null = null;
  private timer: unknown = null;
  private readonly clock: ScrubClock;
  private target: ScrubTarget | null = null;

  constructor(clock: ScrubClock) {
    this.clock = clock;
  }

  press(direction: 1 | -1, current: number, duration: number, target: ScrubTarget): void {
    this.target = target;
    const now = this.clock.now();
    const session = this.session && this.session.direction === direction ? this.session : null;
    if (session && now - session.lastStepAt < SCRUB_STEP_INTERVAL_MS) {
      this.armCommit();
      return;
    }
    const origin = session ? session.target : this.session ? this.session.target : current;
    const startedAt = session ? session.startedAt : now;
    const upper = duration > 0 ? duration : Number.POSITIVE_INFINITY;
    const next = Math.min(upper, Math.max(0, origin + direction * scrubStep(now - startedAt)));
    this.session = { direction, startedAt, lastStepAt: now, target: next };
    target.onPreview(next);
    this.armCommit();
  }

  cancel(): void {
    if (this.timer !== null) this.clock.clearTimer(this.timer);
    this.timer = null;
    this.session = null;
  }

  private armCommit(): void {
    if (this.timer !== null) this.clock.clearTimer(this.timer);
    this.timer = this.clock.setTimer(() => {
      const session = this.session;
      this.timer = null;
      this.session = null;
      if (session) this.target?.onCommit(session.target);
    }, SCRUB_COMMIT_DELAY_MS);
  }
}
