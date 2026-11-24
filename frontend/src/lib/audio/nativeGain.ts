const RAMP_STEP_MS = 25;

export function clampUnitGain(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export function interpolateGain(from: number, to: number, elapsedMs: number, durationMs: number): number {
  if (durationMs <= 0 || elapsedMs >= durationMs) return clampUnitGain(to);
  if (elapsedMs <= 0) return clampUnitGain(from);
  const ratio = elapsedMs / durationMs;
  return clampUnitGain(from + (to - from) * ratio);
}

export interface NativeFader {
  get: () => number;
  set: (value: number) => void;
  rampFrom: (from: number, to: number, durationMs: number) => void;
  rampTo: (to: number, durationMs: number) => void;
  cancel: () => void;
}

export function createNativeFader(getElement: () => HTMLMediaElement | null, initial = 1): NativeFader {
  let value = clampUnitGain(initial);
  let timer: ReturnType<typeof setInterval> | null = null;

  const applyVolume = (next: number) => {
    value = clampUnitGain(next);
    const el = getElement();
    if (el) el.volume = value;
  };

  const cancel = () => {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  };

  const set = (next: number) => {
    cancel();
    applyVolume(next);
  };

  const rampFrom = (from: number, to: number, durationMs: number) => {
    cancel();
    const startValue = clampUnitGain(from);
    const endValue = clampUnitGain(to);
    applyVolume(startValue);
    if (durationMs <= RAMP_STEP_MS || startValue === endValue) {
      applyVolume(endValue);
      return;
    }
    const startedAt = Date.now();
    timer = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      applyVolume(interpolateGain(startValue, endValue, elapsed, durationMs));
      if (elapsed >= durationMs) cancel();
    }, RAMP_STEP_MS);
  };

  const rampTo = (to: number, durationMs: number) => rampFrom(value, to, durationMs);

  return { get: () => value, set, rampFrom, rampTo, cancel };
}
