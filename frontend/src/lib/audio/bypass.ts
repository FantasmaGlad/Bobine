export interface BypassStage {
  input: AudioNode;
  output: AudioNode;
  setBypassed: (bypassed: boolean) => void;
  isBypassed: () => boolean;
}

export function createBypassStage(
  ctx: AudioContext,
  innerInput: AudioNode,
  innerOutput: AudioNode,
  initialBypassed: boolean,
): BypassStage {
  const input = ctx.createGain();
  const output = ctx.createGain();
  input.gain.value = 1;
  output.gain.value = 1;
  let bypassed: boolean | null = null;

  const setBypassed = (next: boolean) => {
    if (bypassed === next) return;
    if (bypassed === true) {
      input.disconnect(output);
    } else if (bypassed === false) {
      input.disconnect(innerInput);
      innerOutput.disconnect(output);
    }
    if (next) {
      input.connect(output);
    } else {
      input.connect(innerInput);
      innerOutput.connect(output);
    }
    bypassed = next;
  };

  setBypassed(initialBypassed);
  return { input, output, setBypassed, isBypassed: () => bypassed === true };
}
