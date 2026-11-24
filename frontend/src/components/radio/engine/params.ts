import {
  rampParamLinear,
  rampParamLinearFrom,
  setParamImmediate,
  type AutomatableParam,
} from "../../../lib/audio/params.ts";

export type ScheduledParam = AutomatableParam;

export const setParamNow = setParamImmediate;
export const rampParamFrom = rampParamLinearFrom;
export const rampParam = rampParamLinear;
