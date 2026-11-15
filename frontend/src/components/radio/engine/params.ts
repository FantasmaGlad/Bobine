export interface ScheduledParam {
  value: number;
  cancelScheduledValues(time: number): unknown;
  setValueAtTime(value: number, time: number): unknown;
  linearRampToValueAtTime(value: number, time: number): unknown;
}

export function setParamNow(param: ScheduledParam, value: number, now: number) {
  param.cancelScheduledValues(now);
  param.setValueAtTime(value, now);
}

export function rampParamFrom(param: ScheduledParam, from: number, to: number, durationMs: number, now: number) {
  param.cancelScheduledValues(now);
  param.setValueAtTime(from, now);
  param.linearRampToValueAtTime(to, now + Math.max(0.001, durationMs / 1000));
}

export function rampParam(param: ScheduledParam, to: number, durationMs: number, now: number) {
  rampParamFrom(param, param.value, to, durationMs, now);
}
