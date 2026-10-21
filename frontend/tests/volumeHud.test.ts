import { test } from "node:test";
import assert from "node:assert/strict";
import { adjustMediaVolume, stepVolume, VOLUME_STEP } from "../src/lib/volumeHud.ts";

test("pas de volume : borné à [0, 1] et sans dérive de flottants", () => {
  let level = 0.5;
  for (let i = 0; i < 3; i++) level = stepVolume(level, VOLUME_STEP);
  assert.equal(level, 0.65);
  assert.equal(stepVolume(0.98, VOLUME_STEP), 1);
  assert.equal(stepVolume(0.02, -VOLUME_STEP), 0);
});

test("réglage commun à tous les éléments, à partir du premier", () => {
  const a = { volume: 0.5, muted: false };
  const b = { volume: 1, muted: true };
  const state = adjustMediaVolume([null, a, undefined, b], VOLUME_STEP);
  assert.deepEqual(state, { level: 0.55, muted: false });
  assert.deepEqual([a, b], [{ volume: 0.55, muted: false }, { volume: 0.55, muted: false }]);
});

test("niveau 0 = sourdine ; sourdine bascule sans toucher au niveau ; sans élément : repli neutre", () => {
  const el = { volume: 0.05, muted: false };
  assert.deepEqual(adjustMediaVolume([el], -VOLUME_STEP), { level: 0, muted: true });
  assert.deepEqual(adjustMediaVolume([el], VOLUME_STEP), { level: 0.05, muted: false });
  const loud = { volume: 0.8, muted: false };
  assert.deepEqual(adjustMediaVolume([loud], 0, true), { level: 0.8, muted: true });
  assert.deepEqual(adjustMediaVolume([], VOLUME_STEP, false), { level: 1, muted: false });
});
