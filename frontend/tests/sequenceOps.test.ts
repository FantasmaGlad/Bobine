import assert from "node:assert/strict";
import test from "node:test";

import { insertItem, moveItem, reorderItem } from "../src/lib/sequenceOps.ts";

test("monter ou descendre échange avec le voisin, sans sortir des bornes", () => {
  assert.deepEqual(moveItem(["a", "b", "c"], 1, -1), ["b", "a", "c"]);
  assert.deepEqual(moveItem(["a", "b", "c"], 1, 1), ["a", "c", "b"]);
  const items = ["a", "b"];
  assert.equal(moveItem(items, 0, -1), items);
  assert.equal(moveItem(items, 1, 1), items);
});

test("réordonner déplace un élément vers sa nouvelle place", () => {
  assert.deepEqual(reorderItem(["a", "b", "c", "d"], 0, 2), ["b", "c", "a", "d"]);
  assert.deepEqual(reorderItem(["a", "b", "c", "d"], 3, 0), ["d", "a", "b", "c"]);
});

test("insérer place l'élément à l'indice voulu, ou à la fin", () => {
  assert.deepEqual(insertItem(["a", "b"], "x", 1), ["a", "x", "b"]);
  assert.deepEqual(insertItem(["a", "b"], "x", null), ["a", "b", "x"]);
  const items = ["a"];
  insertItem(items, "x", 0);
  assert.deepEqual(items, ["a"]);
});
