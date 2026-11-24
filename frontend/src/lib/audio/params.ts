export const SMOOTHING_TIME_CONSTANT = 0.03;

export interface AutomatableParam {
  value: number;
  cancelScheduledValues(time: number): unknown;
  cancelAndHoldAtTime?(time: number): unknown;
  setValueAtTime(value: number, time: number): unknown;
  setTargetAtTime?(value: number, time: number, timeConstant: number): unknown;
  linearRampToValueAtTime?(value: number, time: number): unknown;
}

export function holdParam(param: AutomatableParam, now: number): void {
  if (typeof param.cancelAndHoldAtTime === "function") {
    param.cancelAndHoldAtTime(now);
    return;
  }
  const current = param.value;
  param.cancelScheduledValues(now);
  param.setValueAtTime(current, now);
}

export function setParam(param: AutomatableParam, value: number, now: number, smooth: boolean): void {
  if (smooth && typeof param.setTargetAtTime === "function") {
    holdParam(param, now);
    param.setTargetAtTime(value, now, SMOOTHING_TIME_CONSTANT);
    return;
  }
  param.cancelScheduledValues(now);
  param.setValueAtTime(value, now);
}

export function setParamImmediate(param: AutomatableParam, value: number, now: number): void {
  param.cancelScheduledValues(now);
  param.setValueAtTime(value, now);
}

export function rampParamLinearFrom(
  param: AutomatableParam,
  from: number,
  to: number,
  durationMs: number,
  now: number,
): void {
  param.cancelScheduledValues(now);
  param.setValueAtTime(from, now);
  param.linearRampToValueAtTime?.(to, now + Math.max(0.001, durationMs / 1000));
}

export function rampParamLinear(
  param: AutomatableParam,
  to: number,
  durationMs: number,
  now: number,
): void {
  holdParam(param, now);
  param.linearRampToValueAtTime?.(to, now + Math.max(0.001, durationMs / 1000));
}
