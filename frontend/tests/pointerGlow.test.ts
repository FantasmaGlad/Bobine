import { test } from "node:test";
import assert from "node:assert/strict";
import { relativePosition, shouldGlow } from "../src/lib/pointerGlow.ts";

test("le halo n'existe que pour une souris précise, hors mode sobre", () => {
  assert.equal(shouldGlow({ finePointer: true, reducedMotion: false, remoteMode: false }), true);
  assert.equal(shouldGlow({ finePointer: false, reducedMotion: false, remoteMode: false }), false); // toucher
  assert.equal(shouldGlow({ finePointer: true, reducedMotion: true, remoteMode: false }), false); // mouvement réduit
  assert.equal(shouldGlow({ finePointer: true, reducedMotion: false, remoteMode: true }), false); // télécommande
});

test("position relative bornée au rectangle", () => {
  const rect = { left: 100, top: 50, width: 200, height: 40 };
  assert.deepEqual(relativePosition(rect, 150, 60), { x: 50, y: 10 });
  assert.deepEqual(relativePosition(rect, 10, 500), { x: 0, y: 40 });
  assert.deepEqual(relativePosition(rect, 900, -5), { x: 200, y: 0 });
});
