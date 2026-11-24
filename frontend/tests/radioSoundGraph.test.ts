import { test } from "node:test";
import assert from "node:assert/strict";
import { createSoundChain } from "../src/lib/radioSoundGraph.ts";
import { applyPreset, defaultSound } from "../src/lib/radioSound.ts";

class FakeParam {
  value = 0;
  calls: Array<{ kind: string; value?: number }> = [];
  cancelScheduledValues() {
    this.calls.push({ kind: "cancel" });
  }
  cancelAndHoldAtTime() {
    this.calls.push({ kind: "hold" });
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
  disconnect(target?: FakeNode) {
    this.targets = target ? this.targets.filter((t) => t !== target) : [];
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
class FakeWaveShaper extends FakeNode {
  curve: Float32Array | null = null;
  oversample = "none";
}
class FakeContext {
  currentTime = 0;
  biquads: FakeBiquad[] = [];
  gains: FakeGain[] = [];
  compressors: FakeCompressor[] = [];
  shapers: FakeWaveShaper[] = [];
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
  createWaveShaper() {
    const w = new FakeWaveShaper("shaper");
    this.shapers.push(w);
    return w;
  }
}

function build(includeLimiter = true) {
  const ctx = new FakeContext();
  const destination = new FakeNode("destination");
  const chain = createSoundChain(ctx as unknown as AudioContext, destination as unknown as AudioNode, defaultSound(), { includeLimiter });
  return { ctx, destination, chain };
}

function walkPath(start: FakeNode, destination: FakeNode): string[] {
  let node = start;
  const visited: string[] = [];
  while (node !== destination) {
    visited.push(node.name);
    assert.equal(node.targets.length, 1, "chaîne linéaire : un seul successeur");
    node = node.targets[0];
  }
  return visited;
}

test("à plat, égaliseur et limiteur sont contournés dans le graphe ; avec renfort, toute la chaîne s'engage", () => {
  const { ctx, destination, chain } = build(true);
  assert.equal(ctx.biquads.length, 8);
  assert.equal(ctx.compressors.length, 1);
  assert.equal(ctx.shapers.length, 1);
  assert.equal(chain.isBypassed(), true);
  assert.deepEqual(walkPath(chain.input as unknown as FakeNode, destination), ["gain", "gain", "gain", "gain"]);

  chain.apply(applyPreset("bass", defaultSound()));
  assert.equal(chain.isBypassed(), false);
  const engaged = walkPath(chain.input as unknown as FakeNode, destination);
  assert.equal(engaged.filter((n) => n === "biquad").length, 8);
  assert.equal(engaged.filter((n) => n === "compressor").length, 1);
  assert.equal(engaged.filter((n) => n === "shaper").length, 1);
});

test("sans limiteur intégré (chaîne reliée au mixeur), aucun compresseur redondant n'est créé", () => {
  const { ctx } = build(false);
  assert.equal(ctx.compressors.length, 0);
  assert.equal(ctx.shapers.length, 0);
});

test("les filtres reçoivent leur type et leur fréquence à la création", () => {
  const { ctx } = build();
  assert.deepEqual(ctx.biquads.slice(0, 5).map((b) => b.type), ["lowshelf", "peaking", "peaking", "peaking", "highshelf"]);
  assert.deepEqual(ctx.biquads.slice(0, 5).map((b) => b.frequency.value), [60, 230, 910, 3600, 14000]);
});

test("état initial appliqué sans lissage, changements suivants maintenus puis lissés", () => {
  const { ctx, chain } = build();
  const band0 = ctx.biquads[0].gain;
  assert.ok(band0.calls.some((c) => c.kind === "set"), "initial : valeur posée directement");
  assert.ok(!band0.calls.some((c) => c.kind === "target"));
  chain.apply(applyPreset("bass", defaultSound()));
  assert.ok(band0.calls.some((c) => c.kind === "hold"), "changement : maintien avant transition");
  assert.ok(band0.calls.some((c) => c.kind === "target"), "changement : setTargetAtTime");
  assert.ok(band0.value > 0);
});

test("le préampli compense un relèvement et le limiteur s'engage puis se contourne au retour à plat", () => {
  const { ctx, destination, chain } = build();
  chain.apply({ ...defaultSound(), bands: [6, 0, 0, 0, 0], bass_boost: 6, limiter: true });
  assert.ok(ctx.compressors[0].ratio.value > 1);
  assert.equal(walkPath(chain.input as unknown as FakeNode, destination).includes("compressor"), true);
  chain.apply({ ...defaultSound(), bands: [6, 0, 0, 0, 0], limiter: false });
  assert.equal(ctx.compressors[0].ratio.value, 1);
  assert.equal(walkPath(chain.input as unknown as FakeNode, destination).includes("compressor"), false);
  chain.apply({ ...defaultSound(), limiter: true });
  assert.equal(chain.isBypassed(), true);
  assert.equal(ctx.compressors[0].ratio.value, 1);
});

test("son neutre : tous les gains de filtres retombent à 0 dB et les filtres sont déconnectés", () => {
  const { ctx, chain } = build();
  chain.apply({ ...applyPreset("voice", defaultSound()), enabled: true });
  assert.ok(ctx.biquads.some((b) => b.gain.value !== 0));
  assert.equal(chain.isBypassed(), false);
  chain.apply({ ...applyPreset("voice", defaultSound()), enabled: false });
  assert.ok(ctx.biquads.every((b) => b.gain.value === 0));
  assert.equal(chain.isBypassed(), true);
});
