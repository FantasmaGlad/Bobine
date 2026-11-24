import { createEqualizerStage } from "./audio/equalizer.ts";
import { createSafetyLimiter, type SafetyLimiterStage } from "./audio/safetyLimiter.ts";
import { toGraphParams, type RadioSoundSettings } from "./radioSound.ts";

export { setParam } from "./audio/params.ts";

export interface SoundChainOptions {
  includeLimiter?: boolean;
}

export interface SoundChain {
  input: AudioNode;
  apply: (sound: RadioSoundSettings, smooth?: boolean) => void;
  isBypassed: () => boolean;
}

export function createSoundChain(
  ctx: AudioContext,
  destination: AudioNode,
  initial: RadioSoundSettings,
  options: SoundChainOptions = {},
): SoundChain {
  const includeLimiter = options.includeLimiter ?? true;
  let safety: SafetyLimiterStage | null = null;
  let eqTarget = destination;
  if (includeLimiter) {
    safety = createSafetyLimiter(ctx, destination, toGraphParams(initial).limiter);
    eqTarget = safety.input;
  }
  const equalizer = createEqualizerStage(ctx, eqTarget, initial);

  const apply = (sound: RadioSoundSettings, smooth = true) => {
    equalizer.apply(sound, smooth);
    if (safety) safety.apply(toGraphParams(sound).limiter, ctx.currentTime, smooth);
  };

  return {
    input: equalizer.input,
    apply,
    isBypassed: () => equalizer.isBypassed() && (safety ? safety.isBypassed() : true),
  };
}
