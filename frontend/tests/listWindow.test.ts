import assert from "node:assert/strict";
import test from "node:test";

import { dropIndex, visibleRange } from "../src/lib/listWindow.ts";

test("la fenêtre couvre la vue et une marge de chaque côté", () => {
  assert.deepEqual(visibleRange(0, 420, 72, 3000, 8), [0, 14]);
  assert.deepEqual(visibleRange(7200, 420, 72, 3000, 8), [92, 114]);
  assert.deepEqual(visibleRange(215000, 420, 72, 3000, 8), [2978, 3000]);
  assert.deepEqual(visibleRange(0, 420, 72, 3, 8), [0, 3]);
  assert.deepEqual(visibleRange(0, 420, 72, 0, 8), [0, 0]);
});

test("l'emplacement de dépôt suit l'ancien calcul par bas de ligne", () => {
  const pitch = 72;
  const rowHeight = 64;
  const count = 50;
  const bottoms = Array.from({ length: count }, (_, i) => i * pitch + rowHeight);
  const legacy = (y: number) => {
    const i = bottoms.findIndex((bottom) => y < bottom);
    return i < 0 ? count - 1 : i;
  };
  for (let y = -20; y < count * pitch + 40; y += 1) assert.equal(dropIndex(y, pitch, rowHeight, count), legacy(y), `y=${y}`);
});
