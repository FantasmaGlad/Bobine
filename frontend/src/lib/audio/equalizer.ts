import { isNeutralSound, toGraphParams, type FilterParams, type RadioSoundSettings } from "../radioSound.ts";
import { createBypassStage } from "./bypass.ts";
import { setParam } from "./params.ts";

export interface EqualizerStage {
  input: AudioNode;
  apply: (sound: RadioSoundSettings, smooth?: boolean) => void;
  isBypassed: () => boolean;
}

function createFilter(ctx: AudioContext, params: FilterParams): BiquadFilterNode {
  const node = ctx.createBiquadFilter();
  node.type = params.type;
  node.frequency.value = params.frequency;
  node.Q.value = params.q;
  node.gain.value = 0;
  return node;
}

export function createEqualizerStage(
  ctx: AudioContext,
  destination: AudioNode,
  initial: RadioSoundSettings,
): EqualizerStage {
  const spec = toGraphParams(initial);
  const preamp = ctx.createGain();
  const bandNodes = spec.bands.map((band) => createFilter(ctx, band));
  const bass = createFilter(ctx, spec.bass);
  const loudnessLow = createFilter(ctx, spec.loudnessLow);
  const loudnessHigh = createFilter(ctx, spec.loudnessHigh);

  const nodes: AudioNode[] = [preamp, ...bandNodes, bass, loudnessLow, loudnessHigh];
  for (let i = 0; i < nodes.length - 1; i++) nodes[i].connect(nodes[i + 1]);

  const bypass = createBypassStage(ctx, preamp, loudnessHigh, isNeutralSound(initial));
  bypass.output.connect(destination);

  const apply = (sound: RadioSoundSettings, smooth = true) => {
    const p = toGraphParams(sound);
    const now = ctx.currentTime;
    setParam(preamp.gain, p.preampGain, now, smooth);
    p.bands.forEach((band, i) => setParam(bandNodes[i].gain, band.gain, now, smooth));
    setParam(bass.gain, p.bass.gain, now, smooth);
    setParam(loudnessLow.gain, p.loudnessLow.gain, now, smooth);
    setParam(loudnessHigh.gain, p.loudnessHigh.gain, now, smooth);
    bypass.setBypassed(isNeutralSound(sound));
  };

  apply(initial, false);
  return { input: bypass.input, apply, isBypassed: bypass.isBypassed };
}
