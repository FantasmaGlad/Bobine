import { test } from "node:test";
import assert from "node:assert/strict";
import { createSoundChain } from "../src/lib/radioSoundGraph.ts";
import { applyPreset, defaultSound } from "../src/lib/radioSound.ts";

// Faux AudioContext minimal : trace le câblage et les appels de paramètres, sans audio réel.
class FakeParam {
  value = 0;
  calls: Array<{ kind: string; value?: number }> = [];
  cancelScheduledValues() {
    this.calls.push({ kind: "cancel" });
  }
  setValueAtTime(value: number) {
    this.value = value;
    this.calls.push({ kind: "set", value });
  }
  setTargetAtTime(value: number) {
    this.value = value;
    this.calls.push({ kind: "target", value });
  }
}
class FakeNode {
  name: string;
  targets: FakeNode[] = [];
  constructor(name: string) {
    this.name = name;
  }
  connect(target: FakeNode) {
    this.targets.push(target);
    return target;
  }
}
class FakeGain extends FakeNode {
  gain = new FakeParam();
}
class FakeBiquad extends FakeNode {
  type = "";
  frequency = new FakeParam();
  Q = new FakeParam();
  gain = new FakeParam();
}
class FakeCompressor extends FakeNode {
  threshold = new FakeParam();
  knee = new FakeParam();
  ratio = new FakeParam();
  attack = new FakeParam();
  release = new FakeParam();
}
class FakeContext {
  currentTime = 0;
  biquads: FakeBiquad[] = [];
  gains: FakeGain[] = [];
  compressors: FakeCompressor[] = [];
  createGain() {
    const g = new FakeGain("gain");
    this.gains.push(g);
    return g;
  }
  createBiquadFilter() {
    const b = new FakeBiquad("biquad");
    this.biquads.push(b);
    return b;
  }
  createDynamicsCompressor() {
    const c = new FakeCompressor("compressor");
    this.compressors.push(c);
    return c;
  }
}

function build() {
  const ctx = new FakeContext();
  const destination = new FakeNode("destination");
  const chain = createSoundChain(ctx as unknown as AudioContext, destination as unknown as AudioNode, defaultSound());
  return { ctx, destination, chain };
}

test("la chaîne relie préampli, 5 bandes, basses, loudness x2 et limiteur à la sortie, dans l'ordre", () => {
  const { ctx, destination, chain } = build();
  assert.equal(ctx.biquads.length, 8); // 5 bandes + basses + 2 loudness
  assert.equal(ctx.gains.length, 1); // préampli seul
  assert.equal(ctx.compressors.length, 1);
  let node = chain.input as unknown as FakeNode;
  const visited: string[] = [];
  while (node !== (destination as FakeNode)) {
    visited.push(node.name);
    assert.equal(node.targets.length, 1, "chaîne linéaire : un seul successeur");
    node = node.targets[0];
  }
  assert.deepEqual(visited, ["gain", "biquad", "biquad", "biquad", "biquad", "biquad", "biquad", "biquad", "biquad", "compressor"]);
});

test("les filtres reçoivent leur type et leur fréquence à la création", () => {
  const { ctx } = build();
  assert.deepEqual(ctx.biquads.slice(0, 5).map((b) => b.type), ["lowshelf", "peaking", "peaking", "peaking", "highshelf"]);
  assert.deepEqual(ctx.biquads.slice(0, 5).map((b) => b.frequency.value), [60, 230, 910, 3600, 14000]);
});

test("état initial appliqué sans lissage, changements suivants lissés", () => {
  const { ctx, chain } = build();
  const band0 = ctx.biquads[0].gain;
  assert.ok(band0.calls.some((c) => c.kind === "set"), "initial : valeur posée directement");
  assert.ok(!band0.calls.some((c) => c.kind === "target"));
  chain.apply(applyPreset("bass", defaultSound()));
  assert.ok(band0.calls.some((c) => c.kind === "target"), "changement : setTargetAtTime");
  assert.ok(band0.value > 0);
});

test("le préampli compense un relèvement et le limiteur devient actif puis transparent", () => {
  const { ctx, chain } = build();
  chain.apply({ ...defaultSound(), bands: [6, 0, 0, 0, 0], bass_boost: 6, limiter: true });
  assert.ok(ctx.gains[0].gain.value < 1);
  assert.ok(ctx.compressors[0].ratio.value > 1);
  chain.apply({ ...defaultSound(), bands: [6, 0, 0, 0, 0], limiter: false });
  assert.equal(ctx.compressors[0].ratio.value, 1);
  chain.apply({ ...defaultSound(), limiter: true });
  assert.equal(ctx.gains[0].gain.value, 1);
  assert.equal(ctx.compressors[0].ratio.value, 1);
});

test("son neutre : tous les gains de filtres retombent à 0 dB", () => {
  const { ctx, chain } = build();
  chain.apply({ ...applyPreset("cardio", defaultSound()), enabled: true });
  assert.ok(ctx.biquads.some((b) => b.gain.value !== 0));
  chain.apply({ ...applyPreset("cardio", defaultSound()), enabled: false });
  assert.ok(ctx.biquads.every((b) => b.gain.value === 0));
});
