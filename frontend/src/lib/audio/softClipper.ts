export const CEILING_KNEE_LINEAR = 0.92;
export const CEILING_MAX_LINEAR = 0.99;
export const CEILING_INPUT_HEADROOM = 4;
export const CEILING_CURVE_SAMPLES = 8192;

let cachedCurve: Float32Array<ArrayBuffer> | null = null;

export function buildSoftClipCurve(
  knee = CEILING_KNEE_LINEAR,
  ceiling = CEILING_MAX_LINEAR,
  headroom = CEILING_INPUT_HEADROOM,
  samples = CEILING_CURVE_SAMPLES,
): Float32Array<ArrayBuffer> {
  const curve = new Float32Array(new ArrayBuffer(samples * Float32Array.BYTES_PER_ELEMENT));
  const range = Math.max(1e-6, ceiling - knee);
  for (let i = 0; i < samples; i++) {
    const x = ((i * 2) / (samples - 1) - 1) * headroom;
    const ax = Math.abs(x);
    curve[i] = ax <= knee ? x : Math.sign(x) * (knee + range * Math.tanh((ax - knee) / range));
  }
  return curve;
}

function defaultCurve(): Float32Array<ArrayBuffer> {
  if (!cachedCurve) cachedCurve = buildSoftClipCurve();
  return cachedCurve;
}

export interface SoftClipperStage {
  input: AudioNode;
  output: AudioNode;
}

export function createSoftClipper(ctx: AudioContext): SoftClipperStage {
  if (typeof ctx.createWaveShaper !== "function") {
    const pass = ctx.createGain();
    pass.gain.value = 1;
    return { input: pass, output: pass };
  }
  const pre = ctx.createGain();
  pre.gain.value = 1 / CEILING_INPUT_HEADROOM;
  const shaper = ctx.createWaveShaper();
  shaper.curve = defaultCurve();
  shaper.oversample = "4x";
  pre.connect(shaper);
  return { input: pre, output: shaper };
}
