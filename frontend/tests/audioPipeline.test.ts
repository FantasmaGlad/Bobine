import { test } from "node:test";
import assert from "node:assert/strict";
import { holdParam, setParam } from "../src/lib/audio/params.ts";
import { buildSoftClipCurve, CEILING_KNEE_LINEAR, CEILING_MAX_LINEAR } from "../src/lib/audio/softClipper.ts";
import { clampUnitGain, interpolateGain } from "../src/lib/audio/nativeGain.ts";
import { needsWebAudioGraph } from "../src/lib/audio/radioGraphPolicy.ts";
import { clampMix, defaultMix, isNeutralMix } from "../src/lib/radioMix.ts";
import { applyPreset, defaultSound } from "../src/lib/radioSound.ts";
import { OUTPUT_IDS } from "../src/lib/outputs.ts";
import { videoSoundSavePath } from "../src/lib/audio/videoSound.ts";
import { createRadioAudioEngine } from "../src/lib/audio/radioAudioEngine.ts";

test("holdParam utilise cancelAndHoldAtTime quand disponible, sinon ancre la valeur courante", () => {
  const callsWithHold: string[] = [];
  holdParam(
    {
      value: 0.6,
      cancelScheduledValues: () => callsWithHold.push("cancel"),
      cancelAndHoldAtTime: () => callsWithHold.push("hold"),
      setValueAtTime: () => callsWithHold.push("set"),
    },
    10,
  );
  assert.deepEqual(callsWithHold, ["hold"]);

  const callsFallback: Array<[string, number]> = [];
  setParam(
    {
      value: 0.6,
      cancelScheduledValues: (t) => callsFallback.push(["cancel", t]),
      setValueAtTime: (v) => callsFallback.push(["set", v]),
      setTargetAtTime: (v) => callsFallback.push(["target", v]),
    },
    0.9,
    12,
    true,
  );
  assert.deepEqual(callsFallback, [["cancel", 12], ["set", 0.6], ["target", 0.9]]);
});

test("courbe d'écrêtage doux : linéaire sous le coude, strictement sous 1 jusqu'à +12 dBFS", () => {
  const curve = buildSoftClipCurve();
  const mid = (curve.length - 1) / 2;
  assert.ok(Math.abs(curve[Math.floor(mid)]) < 1e-3);
  for (let i = 0; i < curve.length; i++) {
    assert.ok(Math.abs(curve[i]) <= CEILING_MAX_LINEAR + 1e-6);
    if (i > 0) assert.ok(curve[i] >= curve[i - 1], "courbe monotone croissante");
  }
  const idxHalf = Math.round(((0.5 / 4 + 1) / 2) * (curve.length - 1));
  assert.ok(Math.abs(curve[idxHalf] - 0.5) < 2e-3);
  const idxKnee = Math.round(((CEILING_KNEE_LINEAR / 4 + 1) / 2) * (curve.length - 1));
  assert.ok(Math.abs(curve[idxKnee] - CEILING_KNEE_LINEAR) < 2e-3);
  assert.ok(curve[curve.length - 1] < 1.0 && curve[curve.length - 1] > CEILING_KNEE_LINEAR);
});

test("rampe native : interpolation bornée entre 0 et 1", () => {
  assert.equal(clampUnitGain(-0.5), 0);
  assert.equal(clampUnitGain(1.8), 1);
  assert.equal(clampUnitGain(NaN), 0);
  assert.equal(interpolateGain(1, 0, 0, 1000), 1);
  assert.equal(interpolateGain(1, 0, 500, 1000), 0.5);
  assert.equal(interpolateGain(1, 0, 1500, 1000), 0);
  assert.equal(interpolateGain(0, 0.8, 100, 0), 0.8);
});

test("politique de graphe Web Audio : contournement natif total quand son, mix, route et vumètre sont neutres", () => {
  const s = defaultSound();
  const m = defaultMix();
  assert.equal(isNeutralMix(m), true);
  assert.equal(needsWebAudioGraph(s, m, null, false), false);
  assert.equal(needsWebAudioGraph(applyPreset("bass", s), m, null, false), true);
  assert.equal(needsWebAudioGraph(s, clampMix({ master: { gain_db: 2 } }), null, false), true);
  assert.equal(needsWebAudioGraph(s, clampMix({ music: { muted: true } }), null, false), true);
  assert.equal(needsWebAudioGraph(s, clampMix({ announcements: { sound: { bands: [0, 0, 0, 3, 0] } } }), null, false), true);
  assert.equal(needsWebAudioGraph(s, m, { key: "node:x", label: "HDMI", match: ["HDMI"], kind: "hdmi", fallback: "default", state: "routed" }, false), true);
  assert.equal(needsWebAudioGraph(s, m, null, true), true);
});

test("enregistrement du son vidéo : pointe sur la route /outputs/{sortie}/playback/set_sound", () => {
  for (const id of OUTPUT_IDS) {
    assert.equal(videoSoundSavePath(id), `/outputs/${id}/playback/set_sound`);
  }
});

test("moteur radio : reste en lecture native sans AudioContext à plat, puis attache paresseusement avec un seul limiteur", () => {
  const slotA = { volume: 1 } as HTMLAudioElement;
  const slotB = { volume: 1 } as HTMLAudioElement;
  const ann = { volume: 1 } as HTMLAudioElement;
  let contextCreations = 0;
  let compressorCount = 0;
  let closed = false;
  let readyCalls = 0;

  const makeParam = () => ({
    value: 0,
    cancelScheduledValues() {},
    cancelAndHoldAtTime() {},
    setValueAtTime(v: number) { this.value = v; },
    setTargetAtTime(v: number) { this.value = v; },
    linearRampToValueAtTime() {},
  });
  const makeNode = () => ({ connect(t: unknown) { return t; }, disconnect() {} });
  const fakeCtx = {
    currentTime: 0,
    destination: makeNode(),
    createGain: () => ({ ...makeNode(), gain: makeParam() }),
    createBiquadFilter: () => ({ ...makeNode(), type: "", frequency: makeParam(), Q: makeParam(), gain: makeParam() }),
    createDynamicsCompressor: () => {
      compressorCount++;
      return { ...makeNode(), threshold: makeParam(), knee: makeParam(), ratio: makeParam(), attack: makeParam(), release: makeParam() };
    },
    createWaveShaper: () => ({ ...makeNode(), curve: null, oversample: "none" }),
    createMediaElementSource: () => makeNode(),
    resume: () => Promise.resolve(),
    close: () => { closed = true; return Promise.resolve(); },
  };

  const engine = createRadioAudioEngine({
    getSlot: (slot) => (slot === 0 ? slotA : slotB),
    getAnnouncement: () => ann,
    createContext: () => {
      contextCreations++;
      return fakeCtx as unknown as AudioContext;
    },
    onGraphReady: () => { readyCalls++; },
  });

  engine.unlock(0, 0.75);
  assert.equal(contextCreations, 0);
  assert.equal(engine.isAttached(), false);
  assert.equal(slotA.volume, 0.75);
  assert.equal(slotB.volume, 0);

  engine.updatePolicy(defaultSound(), defaultMix(), null, false);
  assert.equal(contextCreations, 0);
  assert.equal(engine.isAttached(), false);

  engine.updatePolicy(applyPreset("bass", defaultSound()), defaultMix(), null, false);
  assert.equal(contextCreations, 1);
  assert.equal(readyCalls, 1);
  assert.equal(engine.isAttached(), true);
  assert.equal(compressorCount, 1);
  assert.equal(slotA.volume, 1);
  assert.equal(engine.getMixStage()?.isLimiterBypassed(), false);

  engine.updatePolicy(defaultSound(), defaultMix(), null, false);
  assert.equal(engine.getMixStage()?.isLimiterBypassed(), true);

  engine.dispose();
  assert.equal(closed, true);
  assert.equal(engine.isAttached(), false);
});
