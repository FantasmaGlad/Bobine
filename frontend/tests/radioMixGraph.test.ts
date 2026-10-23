import { test } from "node:test";
import assert from "node:assert/strict";
import { createMixStage } from "../src/lib/radioMixGraph.ts";
import { clampMix, defaultMix, dbToGain } from "../src/lib/radioMix.ts";

// Faux AudioContext minimal : trace le câblage et les appels de paramètres, sans audio réel.
class FakeParam {
  value = 0;
  setValueAtTime(value: number) { this.value = value; }
  setTargetAtTime(value: number) { this.value = value; }
  cancelScheduledValues() {}
}
class FakeNode {
  targets: FakeNode[] = [];
  name: string;
  constructor(name: string) { this.name = name; }
  connect(target: FakeNode) { this.targets.push(target); return target; }
  disconnect(target?: FakeNode) { this.targets = target ? this.targets.filter((t) => t !== target) : []; }
}
class FakeGain extends FakeNode { gain = new FakeParam(); constructor() { super("gain"); } }
class FakeBiquad extends FakeNode {
  type = ""; frequency = new FakeParam(); Q = new FakeParam(); gain = new FakeParam();
  constructor() { super("biquad"); }
}
class FakeCompressor extends FakeNode {
  threshold = new FakeParam(); knee = new FakeParam(); ratio = new FakeParam(); attack = new FakeParam(); release = new FakeParam();
  constructor() { super("compressor"); }
}
class FakeAnalyser extends FakeNode {
  fftSize = 2048;
  samples: number[] = [];
  constructor() { super("analyser"); }
  getFloatTimeDomainData(buffer: Float32Array) { buffer.fill(0); this.samples.forEach((s, i) => { buffer[i] = s; }); }
}
class FakeContext {
  currentTime = 0;
  gains: FakeGain[] = [];
  compressors: FakeCompressor[] = [];
  analysers: FakeAnalyser[] = [];
  createGain() { const g = new FakeGain(); this.gains.push(g); return g; }
  createBiquadFilter() { return new FakeBiquad(); }
  createDynamicsCompressor() { const c = new FakeCompressor(); this.compressors.push(c); return c; }
  createAnalyser() { const a = new FakeAnalyser(); this.analysers.push(a); return a; }
}

function build(mix = defaultMix()) {
  const ctx = new FakeContext();
  const destination = new FakeNode("destination");
  const stage = createMixStage(ctx as unknown as AudioContext, destination as unknown as AudioNode, mix);
  return { ctx, destination, stage };
}

test("câblage : musique et rappels → sortie → limiteur → porte de route → destination", () => {
  const { ctx, destination, stage } = build();
  const [musicBus, announcementsBus, masterBus] = ctx.gains as unknown as FakeNode[];
  assert.ok((stage.musicInput as unknown as FakeNode) === musicBus);
  assert.ok(musicBus.targets.includes(masterBus) && announcementsBus.targets.includes(masterBus));
  const limiter = ctx.compressors[0];
  assert.ok(masterBus.targets.includes(limiter));
  const routeGate = limiter.targets[0];
  assert.ok(routeGate.targets.includes(destination as unknown as FakeNode));
  // La chaîne des rappels aboutit au fader des rappels (son dernier nœud est son limiteur).
  const announcementsLimiter = ctx.compressors[1];
  assert.ok(announcementsLimiter.targets.includes(announcementsBus));
  assert.equal(stage.announcementsInput === (stage.musicInput as unknown), false);
});

test("réglages initiaux posés sans transition, puis changements appliqués", () => {
  const { ctx, stage } = build(clampMix({ music: { gain_db: -6 }, announcements: { muted: true }, master: { gain_db: -3 } }));
  const [musicBus, announcementsBus, masterBus] = ctx.gains;
  assert.ok(Math.abs(musicBus.gain.value - dbToGain(-6)) < 1e-9);
  assert.equal(announcementsBus.gain.value, 0);
  assert.ok(Math.abs(masterBus.gain.value - dbToGain(-3)) < 1e-9);
  stage.apply(clampMix({ music: { solo: true } }));
  assert.equal(musicBus.gain.value, 1);
  assert.equal(announcementsBus.gain.value, 0); // coupé par le solo de la musique
  assert.equal(masterBus.gain.value, 1);
});

test("limiteur de sortie : transparent à plat, actif quand un fader relève", () => {
  const { ctx, stage } = build();
  const limiter = ctx.compressors[0];
  assert.equal(limiter.ratio.value, 1);
  stage.apply(clampMix({ master: { gain_db: 4 } }));
  assert.equal(limiter.ratio.value, 20);
});

test("sourdine de repli : porte de route seule, mixage intact", () => {
  const { ctx, stage } = build();
  const limiter = ctx.compressors[0];
  const routeGate = limiter.targets[0] as unknown as FakeGain;
  const masterBus = ctx.gains[2];
  assert.equal(routeGate.gain.value, 1);
  stage.setRouteMuted(true);
  assert.equal(routeGate.gain.value, 0);
  assert.equal(masterBus.gain.value, 1);
  stage.setRouteMuted(false);
  assert.equal(routeGate.gain.value, 1);
});

test("vumètres : aucun analyseur tant qu'une interface n'en demande pas, branchés puis débranchés à la demande", () => {
  const { ctx, stage } = build();
  assert.equal(ctx.analysers.length, 0);
  assert.deepEqual(stage.readLevels(), {});
  stage.setMetering(true);
  stage.setMetering(true); // idempotent
  assert.equal(ctx.analysers.length, 3);
  const [musicBus, announcementsBus, masterBus] = ctx.gains;
  assert.ok(musicBus.targets.includes(ctx.analysers[0]) && announcementsBus.targets.includes(ctx.analysers[1]) && masterBus.targets.includes(ctx.analysers[2]));
  ctx.analysers[0].samples = [0.5, -0.25];
  ctx.analysers[2].samples = [1];
  assert.deepEqual(stage.readLevels(), { music: 90, announcements: 0, master: 100 });
  stage.setMetering(false);
  assert.ok(!musicBus.targets.includes(ctx.analysers[0]));
  assert.deepEqual(stage.readLevels(), {});
});
