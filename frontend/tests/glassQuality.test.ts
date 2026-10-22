import { test } from "node:test";
import assert from "node:assert/strict";
import { GLASS_STEPS, MIN_SAMPLE, nextStep, scaleForMode } from "../src/lib/glassQuality.ts";

const frames = (ms: number, n = MIN_SAMPLE) => Array.from({ length: n }, () => ms);

test("un appareil fluide garde le verre complet", () => {
  assert.equal(nextStep(frames(16.7), 0), 0);
});

test("un appareil qui saccade descend d'un palier à la fois", () => {
  assert.equal(nextStep(frames(40), 0), 1);
  assert.equal(nextStep(frames(40), 1), 2);
  assert.equal(nextStep(frames(40), 2), 2, "dernier palier : plus de descente");
});

test("échantillon trop court : aucune décision", () => {
  assert.equal(nextStep(frames(80, MIN_SAMPLE - 1), 0), 0);
});

test("quelques images lentes isolées ne suffisent pas (75e centile)", () => {
  const mostlyFast = [...frames(16.7, MIN_SAMPLE - 8), ...frames(90, 8)];
  assert.equal(nextStep(mostlyFast, 0), 0);
});

test("les modes explicites ignorent le palier automatique", () => {
  assert.equal(scaleForMode("full", 2), GLASS_STEPS[0]);
  assert.equal(scaleForMode("reduced", 0), GLASS_STEPS[1]);
  assert.equal(scaleForMode("off", 0), GLASS_STEPS[2]);
  assert.equal(scaleForMode("auto", 1), GLASS_STEPS[1]);
  assert.equal(scaleForMode("auto", 99), GLASS_STEPS[2], "palier hors bornes ramené au dernier");
});
