import { limiterTrim, toGraphParams, type FilterParams, type LimiterParams, type RadioSoundSettings } from "./radioSound.ts";

const SMOOTHING_TIME_CONSTANT = 0.03;

export interface SoundChain {
  input: AudioNode;
  apply: (sound: RadioSoundSettings, smooth?: boolean) => void;
}

export function applyLimiter(limiter: DynamicsCompressorNode, trim: GainNode, p: LimiterParams, now: number, smooth: boolean): void {
  setParam(limiter.threshold, p.threshold, now, smooth);
  setParam(limiter.knee, p.knee, now, smooth);
  setParam(limiter.ratio, p.ratio, now, smooth);
  setParam(limiter.attack, p.attack, now, smooth);
  setParam(limiter.release, p.release, now, smooth);
  setParam(trim.gain, limiterTrim(p), now, smooth);
}

export function setParam(param: AudioParam, value: number, now: number, smooth: boolean): void {
  param.cancelScheduledValues(now);
  if (smooth) param.setTargetAtTime(value, now, SMOOTHING_TIME_CONSTANT);
  else param.setValueAtTime(value, now);
}

function createFilter(ctx: AudioContext, params: FilterParams): BiquadFilterNode {
  const node = ctx.createBiquadFilter();
  node.type = params.type;
  node.frequency.value = params.frequency;
  node.Q.value = params.q;
  node.gain.value = 0;
  return node;
}

export function createSoundChain(ctx: AudioContext, destination: AudioNode, initial: RadioSoundSettings): SoundChain {
  const neutral = toGraphParams(initial);
  const preamp = ctx.createGain();
  const bandNodes = neutral.bands.map((band) => createFilter(ctx, band));
  const bass = createFilter(ctx, neutral.bass);
  const loudnessLow = createFilter(ctx, neutral.loudnessLow);
  const loudnessHigh = createFilter(ctx, neutral.loudnessHigh);
  const limiter = ctx.createDynamicsCompressor();
  const trim = ctx.createGain();

  const chain: AudioNode[] = [preamp, ...bandNodes, bass, loudnessLow, loudnessHigh, limiter, trim];
  for (let i = 0; i < chain.length - 1; i++) chain[i].connect(chain[i + 1]);
  trim.connect(destination);

  const apply = (sound: RadioSoundSettings, smooth = true) => {
    const p = toGraphParams(sound);
    const now = ctx.currentTime;
    setParam(preamp.gain, p.preampGain, now, smooth);
    p.bands.forEach((band, i) => setParam(bandNodes[i].gain, band.gain, now, smooth));
    setParam(bass.gain, p.bass.gain, now, smooth);
    setParam(loudnessLow.gain, p.loudnessLow.gain, now, smooth);
    setParam(loudnessHigh.gain, p.loudnessHigh.gain, now, smooth);
    applyLimiter(limiter, trim, p.limiter, now, smooth);
  };

  apply(initial, false);
  return { input: preamp, apply };
}
