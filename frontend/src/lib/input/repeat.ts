export const REPEAT_DELAY_MS = 350;
export const REPEAT_RATE_MS = 140;

export class ButtonRepeat {
  private readonly held = new Map<string, { since: number; step: number }>();

  fires(key: string, pressed: boolean, repeats: boolean, now: number): boolean {
    const state = this.held.get(key);
    if (!pressed) {
      this.held.delete(key);
      return false;
    }
    if (!state) {
      this.held.set(key, { since: now, step: 0 });
      return true;
    }
    if (!repeats) return false;
    const elapsed = now - state.since;
    if (elapsed < REPEAT_DELAY_MS) return false;
    const step = Math.floor((elapsed - REPEAT_DELAY_MS) / REPEAT_RATE_MS);
    if (step <= state.step) return false;
    state.step = step;
    return true;
  }
}
