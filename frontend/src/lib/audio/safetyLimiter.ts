import { limiterTrim, type LimiterParams } from "../radioSound.ts";
import { createBypassStage } from "./bypass.ts";
import { setParam } from "./params.ts";
import { createSoftClipper } from "./softClipper.ts";

export interface SafetyLimiterStage {
  input: AudioNode;
  apply: (params: LimiterParams, now: number, smooth: boolean) => void;
  isBypassed: () => boolean;
}

export function isLimiterBypassed(params: LimiterParams): boolean {
  return params.ratio <= 1;
}

export function applyCompressorParams(
  limiter: DynamicsCompressorNode,
  trim: GainNode,
  params: LimiterParams,
  now: number,
  smooth: boolean,
): void {
  setParam(limiter.threshold, params.threshold, now, smooth);
  setParam(limiter.knee, params.knee, now, smooth);
  setParam(limiter.ratio, params.ratio, now, smooth);
  setParam(limiter.attack, params.attack, now, smooth);
  setParam(limiter.release, params.release, now, smooth);
  setParam(trim.gain, limiterTrim(params), now, smooth);
}

export function createSafetyLimiter(
  ctx: AudioContext,
  destination: AudioNode,
  initial: LimiterParams,
): SafetyLimiterStage {
  const compressor = ctx.createDynamicsCompressor();
  const trim = ctx.createGain();
  const clipper = createSoftClipper(ctx);
  compressor.connect(trim);
  trim.connect(clipper.input);

  const bypass = createBypassStage(ctx, compressor, clipper.output, isLimiterBypassed(initial));
  bypass.output.connect(destination);

  const apply = (params: LimiterParams, now: number, smooth: boolean) => {
    applyCompressorParams(compressor, trim, params, now, smooth);
    bypass.setBypassed(isLimiterBypassed(params));
  };

  apply(initial, ctx.currentTime, false);
  return { input: bypass.input, apply, isBypassed: bypass.isBypassed };
}
